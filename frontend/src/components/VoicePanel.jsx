import { useEffect, useRef, useState } from 'react'

const WS_BASE = (import.meta.env.VITE_WS_URL || '').replace(/\/$/, '')

function wsUrl() {
  if (WS_BASE) return `${WS_BASE}/ws/voice`
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/voice`
}

function floatTo16BitPCM(float32) {
  const out = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out
}

function b64ToBytes(b64) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

export default function VoicePanel() {
  const [status, setStatus] = useState('idle')
  const [gender, setGender] = useState('female')
  const [transcript, setTranscript] = useState('')
  const [reply, setReply] = useState('')
  const [ttfa, setTtfa] = useState(null)
  const [error, setError] = useState('')
  const wsRef = useRef(null)
  const ctxRef = useRef(null)
  const procRef = useRef(null)
  const streamRef = useRef(null)
  const audioRef = useRef(null)
  const queueRef = useRef([])
  const playingRef = useRef(false)

  useEffect(() => {
    audioRef.current = new Audio()
    audioRef.current.onended = () => { playingRef.current = false; playNext() }
    return () => stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const playNext = async () => {
    if (playingRef.current) return
    const next = queueRef.current.shift()
    if (!next) return
    playingRef.current = true
    const blob = new Blob([next], { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)
    audioRef.current.src = url
    try { await audioRef.current.play() } catch { playingRef.current = false }
  }

  const stopPlayback = () => {
    queueRef.current = []
    playingRef.current = false
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = '' }
  }

  const connectWs = () => new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl())
    wsRef.current = ws
    ws.onopen = () => resolve(ws)
    ws.onerror = () => reject(new Error('voice ws failed'))
    ws.onclose = () => { if (status === 'listening') setStatus('idle') }
    ws.onmessage = async (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'ready') {
        if (msg.gender) setGender(msg.gender)
      } else if (msg.type === 'stt') {
        setTranscript(`[${msg.language}] ${msg.text}`)
      } else if (msg.type === 'assistant_start') {
        setReply('')
      } else if (msg.type === 'assistant_delta') {
        setReply((r) => r + msg.delta)
      } else if (msg.type === 'assistant_text') {
        setReply(msg.text)
      } else if (msg.type === 'tts_chunk') {
        if (msg.ttfa_ms != null) setTtfa(msg.ttfa_ms)
        queueRef.current.push(b64ToBytes(msg.audio_b64))
        playNext()
      } else if (msg.type === 'metrics' && msg.ttfa_ms != null) {
        setTtfa(msg.ttfa_ms)
      } else if (msg.type === 'voice_setting') {
        setGender(msg.gender)
      } else if (msg.type === 'interrupted') {
        stopPlayback()
      } else if (msg.type === 'error') {
        setError(msg.error || 'voice error')
      }
    }
  })

  const start = async () => {
    setError('')
    try {
      const ws = wsRef.current?.readyState === WebSocket.OPEN ? wsRef.current : await connectWs()
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      streamRef.current = stream
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 })
      ctxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      const proc = ctx.createScriptProcessor(4096, 1, 1)
      procRef.current = proc
      proc.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return
        const input = e.inputBuffer.getChannelData(0)
        const pcm16 = floatTo16BitPCM(input)
        const bytes = new Uint8Array(pcm16.buffer)
        let bin = ''
        for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
        ws.send(JSON.stringify({ type: 'audio_chunk', data: btoa(bin), sample_rate: 16000 }))
      }
      source.connect(proc)
      proc.connect(ctx.destination)
      setStatus('listening')
    } catch (e) {
      setError(e.message || 'mic failed')
      setStatus('idle')
    }
  }

  const stop = () => {
    procRef.current?.disconnect()
    ctxRef.current?.close()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    wsRef.current?.close()
    procRef.current = null; ctxRef.current = null; streamRef.current = null; wsRef.current = null
    stopPlayback()
    setStatus('idle')
  }

  const interrupt = () => {
    stopPlayback()
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'interrupt' }))
  }

  const setVoice = (g) => {
    setGender(g)
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'set_voice', gender: g }))
  }

  return (
    <section className="panel voice-panel">
      <div className="panel-head">
        <h2>VOICE ASSISTANT</h2>
        <span>{status === 'listening' ? 'listening' : 'idle'} {ttfa != null ? `TTFA ${ttfa}ms` : ''}</span>
      </div>
      <div className="voice-body">
        <div className="voice-controls">
          <button className="auth-btn" onClick={status === 'listening' ? stop : start}>{status === 'listening' ? 'Stop Mic' : 'Start Mic'}</button>
          <button className="auth-btn small" onClick={interrupt}>Interrupt</button>
          <button className={`auth-btn small ${gender === 'female' ? '' : 'muted-btn'}`} onClick={() => setVoice('female')}>Female</button>
          <button className={`auth-btn small ${gender === 'male' ? '' : 'muted-btn'}`} onClick={() => setVoice('male')}>Male</button>
        </div>
        <div className="voice-line"><span className="voice-label">YOU</span><span>{transcript || '...'}</span></div>
        <div className="voice-line"><span className="voice-label">AI</span><span>{reply || '...'}</span></div>
        {error && <div className="auth-error">{error}</div>}
      </div>
    </section>
  )
}
