import { useEffect, useRef, useState } from 'react'
import { useI18n } from './i18n'
import './ImageStyleQueue.css'

type Job={id:string;name:string;style:string;state:string;attempts:number;download_available:boolean;error:string|null}
export default function ImageStyleQueue(){
  const {t}=useI18n()
  const [jobs,setJobs]=useState<Job[]>([]),[files,setFiles]=useState<File[]>([]),[style,setStyle]=useState('clean')
  const [selected,setSelected]=useState<string[]>([]),[busy,setBusy]=useState(false),[notice,setNotice]=useState('')
  const alive=useRef(true)
  const fileInput=useRef<HTMLInputElement>(null)
  const refresh=async(signal?:AbortSignal)=>{
    const response=await fetch('/api/image/style-queue/jobs',{signal})
    if(!response.ok)throw new Error('queue')
    const value=await response.json();if(alive.current){setJobs(value.jobs);setNotice(current=>current==='unavailable'?'':current)}
  }
  useEffect(()=>{
    alive.current=true;const controller=new AbortController()
    // Only one outstanding status request; polling stops when this view is closed.
    let timer:ReturnType<typeof setTimeout>
    const poll=async()=>{try{await refresh(controller.signal)}catch{if(!controller.signal.aborted)setNotice('unavailable')}finally{if(!controller.signal.aborted)timer=setTimeout(()=>void poll(),1500)}}
    void poll();return()=>{alive.current=false;controller.abort();clearTimeout(timer)}
  },[])
  const submit=async()=>{
    setBusy(true);let failures=0
    for(const file of files){
      if(!alive.current)break
      try{
        if(file.size>64*1024*1024)throw new Error('size')
        const form=new FormData();form.append('file',file);form.append('style',style)
        const response=await fetch('/api/image/style-queue/jobs',{method:'POST',body:form})
        if(!response.ok)throw new Error('submit')
      }catch{failures++}
    }
    if(alive.current){setFiles([]);if(fileInput.current)fileInput.current.value='';setNotice(failures?'partial':'submitted');setBusy(false);void refresh().catch(()=>{})}
  }
  const control=async(job:Job,action:string)=>{
    try{
      const response=await fetch(`/api/image/style-queue/jobs/${job.id}${action==='remove'?'':'/'+action}`,{method:action==='remove'?'DELETE':'POST'})
      if(!response.ok)throw new Error('control')
      setSelected(value=>value.filter(id=>id!==job.id));await refresh()
    }catch{setNotice('failed')}
  }
  const download=async()=>{
    setBusy(true)
    try{
      const response=await fetch('/api/image/style-queue/archive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:selected})})
      if(!response.ok)throw new Error('archive')
      const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download='biofigure-presentations.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),60000)
    }catch{setNotice('archive')}
    finally{if(alive.current)setBusy(false)}
  }
  const states:Record<string,string>={queued:t('排队','Queued'),running:t('处理中','Running'),done:t('完成','Done'),failed:t('失败','Failed'),cancelled:t('已取消','Cancelled'),cancel_requested:t('取消中','Cancelling')}
  const messages:Record<string,string>={unavailable:t('暂时无法读取队列，请检查本机服务。','Queue unavailable. Check the local service.'),partial:t('部分文件未提交，请检查 64 MiB 文件限制、100 项容量和磁盘空间；已提交项保留。','Some files were not submitted. Check the 64 MiB/file, 100-job and disk limits; accepted jobs are retained.'),submitted:t('已提交本机队列。','Submitted to the local queue.'),failed:t('操作失败，请刷新队列后重试。','Action failed. Refresh the queue and retry.'),archive:t('下载失败：请选择已完成的任务，总解包内容不超过 512 MiB。','Download failed. Select completed jobs totaling at most 512 MiB of unpacked content.')}
  return <section className="iw-section image-style-queue" aria-label={t('统一风格处理队列','Unified image presentation queue')}>
    <h2>{t('统一风格处理队列','Unified image presentation queue')}</h2>
    <p>{t('批量统一背景、留白、边框和独立文件名说明。原图数据与嵌入标签不变，不重绘科研内容。每项输出包含原文件、可编辑 SVG 和记录。','Batch-unify background, margins, borders and separate filename captions. Original image data and embedded labels stay intact; scientific content is not repainted. Each output includes its source, editable SVG and manifest.')}</p>
    <p>{t('支持 PNG、RGB JPEG 和单平面 8 位 TIFF；最多 100 项，单文件 64 MiB、1600 万像素，单进程处理。队列保存于本机并可在重启后续作。','PNG, RGB JPEG and single-plane 8-bit TIFF; up to 100 jobs, 64 MiB and 16 million pixels per image, one worker. The local queue survives restart.')}</p>
    <label>{t('统一风格','Shared style')}<select value={style} disabled={busy} onChange={e=>setStyle(e.target.value)}><option value="clean">{t('简洁白底','Clean white')}</option><option value="soft">{t('柔和灰白','Soft neutral')}</option><option value="contrast">{t('清晰边界','Clear contrast')}</option></select></label>
    <div className="isq-file-picker"><input ref={fileInput} type="file" multiple hidden aria-label={t('选择多张图片','Choose multiple images')} accept=".png,.jpg,.jpeg,.tif,.tiff" disabled={busy} onChange={e=>setFiles(Array.from(e.target.files||[]))}/><button type="button" disabled={busy} onClick={()=>fileInput.current?.click()}>{t('选择多张图片','Choose multiple images')}</button><span>{t(`已选择 ${files.length} 张`,`Selected ${files.length} images`)}</span></div>
    <button type="button" disabled={busy||!files.length||files.length>100} onClick={()=>void submit()}>{t(`提交 ${files.length} 张图片`,`Submit ${files.length} images`)}</button>
    <button type="button" disabled={busy||!selected.length} onClick={()=>void download()}>{t('下载所选成品','Download selected outputs')}</button>
    <button type="button" onClick={()=>setSelected(jobs.filter(job=>job.download_available).map(job=>job.id))}>{t('选择已完成项','Select completed')}</button>
    {notice&&<p role="status">{messages[notice]}</p>}
    <ul className="isq-list">{jobs.map(job=><li key={job.id}>
      <label className="isq-select"><input type="checkbox" checked={selected.includes(job.id)} disabled={!job.download_available} onChange={e=>setSelected(value=>e.target.checked?[...value,job.id]:value.filter(id=>id!==job.id))}/><strong>{job.name}</strong></label><span className="isq-state">{states[job.state]||job.state} · {t('尝试','Attempt')} {job.attempts}</span>
      {job.state==='failed'&&<p>{t('此项未完成；请检查格式、方向、单平面、位深、尺寸和磁盘空间。原文件未改动，可单独重试。','This item failed. Check format, orientation, single plane, bit depth, size and disk space. Its source is unchanged; retry independently.')}</p>}
      {['queued','running'].includes(job.state)&&<button type="button" onClick={()=>void control(job,'cancel')}>{t('取消','Cancel')}</button>}
      {['failed','cancelled'].includes(job.state)&&job.attempts<5&&<button type="button" onClick={()=>void control(job,'retry')}>{t('单独重试','Retry item')}</button>}
      {job.download_available&&<a href={`/api/image/style-queue/jobs/${job.id}/download`} download>{t('下载','Download')}</a>}
      {['done','failed','cancelled'].includes(job.state)&&<button type="button" onClick={()=>void control(job,'remove')}>{t('移除队列副本','Remove queue copy')}</button>}
    </li>)}</ul>
  </section>
}
