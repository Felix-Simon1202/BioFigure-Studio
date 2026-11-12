import { useEffect, useId, useRef, useState } from 'react'
import './WorkspaceNavigation.css'

type Item = { label: string; description?: string; onSelect: () => void }
export default function NavigationGroup({ label, description, icon, items, active = false, direction = 'side' }: {
  label: string; description: string; icon?: string; items: Item[]; active?: boolean; direction?: 'side' | 'above'
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null)
  const closing = useRef<ReturnType<typeof setTimeout> | null>(null)
  const id = useId()
  const cancelClose = () => { if (closing.current) clearTimeout(closing.current) }
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', outside)
    return () => { document.removeEventListener('pointerdown', outside); if (closing.current) clearTimeout(closing.current) }
  }, [open])
  return <div className={`nav-group nav-group-${direction}`} ref={root}
    onPointerEnter={event => { if (event.pointerType === 'mouse') { cancelClose(); setOpen(true) } }}
    onPointerLeave={event => { if (event.pointerType === 'mouse') { cancelClose(); closing.current = setTimeout(() => setOpen(false), 160) } }}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}
    onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus() }
    }}>
    <button ref={trigger} type="button" className="nav-group-trigger" aria-expanded={open} aria-controls={id}
      data-active={active || undefined} onClick={() => { cancelClose(); setOpen(value => !value) }}
      onKeyDown={event => {
        if (event.key === 'ArrowDown') {
          event.preventDefault(); setOpen(true)
          setTimeout(() => root.current?.querySelector<HTMLButtonElement>('.nav-group-panel button')?.focus(), 0)
        }
      }}>
      {icon && <span aria-hidden="true" className="nav-group-icon">{icon}</span>}<span>{label}</span><span aria-hidden="true" className="nav-group-chevron">›</span>
    </button>
    <div id={id} className="nav-group-panel" hidden={!open}>
      <strong>{label}</strong><p>{description}</p>
      {items.map(item => <button key={item.label} type="button" onClick={() => { setOpen(false); item.onSelect() }}>
        <span>{item.label}</span>{item.description && <small>{item.description}</small>}
      </button>)}
    </div>
  </div>
}
