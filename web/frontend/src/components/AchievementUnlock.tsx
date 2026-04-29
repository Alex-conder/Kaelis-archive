/**
 * 成就解锁庆祝动画 — AchievementUnlock
 * UX-16: 成就系统与趣味化激励
 */

import { useEffect, useRef, useState } from 'react'
import { Award, X } from 'lucide-react'
import { showToast } from './Toast'

interface Achievement {
  id: string
  name: string
  description: string
  icon?: string
}

interface AchievementUnlockProps {
  achievement: Achievement
  onDismiss?: () => void
}

function ConfettiCanvas({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!active) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = window.innerWidth
    canvas.height = window.innerHeight

    const particles: Array<{
      x: number
      y: number
      vx: number
      vy: number
      color: string
      size: number
      life: number
    }> = []

    const colors = ['#a78bfa', '#60a5fa', '#34d399', '#fbbf24', '#f472b6', '#22d3ee']

    for (let i = 0; i < 80; i++) {
      particles.push({
        x: canvas.width / 2,
        y: canvas.height / 3,
        vx: (Math.random() - 0.5) * 12,
        vy: (Math.random() - 1) * 12 - 2,
        color: colors[Math.floor(Math.random() * colors.length)],
        size: Math.random() * 4 + 2,
        life: 1,
      })
    }

    let animId: number
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      let alive = 0
      particles.forEach((p) => {
        if (p.life <= 0) return
        alive++
        p.x += p.vx
        p.y += p.vy
        p.vy += 0.2 // gravity
        p.life -= 0.015
        ctx.globalAlpha = p.life
        ctx.fillStyle = p.color
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2)
        ctx.fill()
      })
      if (alive > 0) {
        animId = requestAnimationFrame(animate)
      }
    }
    animId = requestAnimationFrame(animate)

    return () => cancelAnimationFrame(animId)
  }, [active])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-[150]"
      style={{ width: '100%', height: '100%' }}
    />
  )
}

export function triggerAchievement(achievement: Achievement) {
  // 写入 localStorage 记录
  try {
    const unlocked = JSON.parse(localStorage.getItem('kaelis_achievements') || '[]')
    if (!unlocked.includes(achievement.id)) {
      unlocked.push(achievement.id)
      localStorage.setItem('kaelis_achievements', JSON.stringify(unlocked))
    }
  } catch {
    // ignore
  }
  showToast(`🎉 解锁成就：${achievement.name}`)
}

export default function AchievementUnlock({ achievement, onDismiss }: AchievementUnlockProps) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false)
      onDismiss?.()
    }, 4000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  if (!visible) return null

  return (
    <>
      <ConfettiCanvas active={true} />
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[160] animate-in slide-in-from-top-2 fade-in duration-300">
        <div className="bg-[#1E293B] border border-purple-500/30 rounded-xl px-5 py-4 shadow-2xl flex items-center gap-4 min-w-[300px]">
          <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center">
            <Award className="w-6 h-6 text-purple-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold text-white">成就解锁！</p>
            <p className="text-sm text-purple-300">{achievement.name}</p>
            <p className="text-xs text-slate-400">{achievement.description}</p>
          </div>
          <button
            onClick={() => { setVisible(false); onDismiss?.() }}
            className="text-slate-500 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  )
}
