// src/workers/mp3EncodeWorker.js

import * as lame from '@breezystack/lamejs'

let mp3Encoder = null
let mp3Data = []

/**
 * 初始化 MP3 编码器
 * @param {number} sampleRate - 采样率
 * @param {number} bitRate - 比特率
 */
function initEncoder(sampleRate, bitRate) {
  // 单声道编码
  mp3Encoder = new lame.Mp3Encoder(1, sampleRate, bitRate)
  mp3Data = []
}

/**
 * 编码一段 PCM 数据
 * @param {ArrayBuffer} pcmBuffer - Int16Array 的 ArrayBuffer
 */
function encodeChunk(pcmBuffer) {
  if (!mp3Encoder) return
  const samples = new Int16Array(pcmBuffer)
  const mp3buf = mp3Encoder.encodeBuffer(samples)
  if (mp3buf.length > 0) {
    mp3Data.push(new Int8Array(mp3buf))
  }
}

/**
 * 完成编码并返回 MP3 Blob
 */
function finishEncoding() {
  if (!mp3Encoder) return null
  const mp3buf = mp3Encoder.flush()
  if (mp3buf.length > 0) {
    mp3Data.push(new Int8Array(mp3buf))
  }

  const blob = new Blob(mp3Data, { type: 'audio/mp3' })

  // 清理状态
  mp3Data = []
  mp3Encoder = null

  return blob
}

self.onmessage = function(event) {
  const { type, buffer, sampleRate, bitRate } = event.data

  switch (type) {
    case 'init':
      initEncoder(sampleRate || 44100, bitRate || 128)
      break
    case 'pcm':
      if (buffer) {
        encodeChunk(buffer)
      }
      break
    case 'stop':
      const mp3Blob = finishEncoding()
      if (mp3Blob) {
        // 将生成的 Blob 发回主线程
        self.postMessage({ type: 'mp3', blob: mp3Blob })
      }
      break
    default:
      console.warn('mp3EncodeWorker: unknown message type', type)
  }
}
