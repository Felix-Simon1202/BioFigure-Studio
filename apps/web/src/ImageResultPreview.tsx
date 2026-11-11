import { useState } from 'react'

export default function ImageResultPreview({ id, width, height, hasAnnotations, revision }: {
  id: string; width: number; height: number; hasAnnotations: boolean; revision: number
}) {
  const [showAnnotations, setShowAnnotations] = useState(true)
  const [failed, setFailed] = useState(false)
  return <section className="iw-preview" aria-label="图像成品预览">
    <h3>检查图像与标注</h3>
    <p>{width} × {height} 源像素。预览会缩放显示，导出的 TIFF 保持原像素。</p>
    <p>高位深灰度按成品有限值的最小—最大范围线性显示；常量图和非有限值显示为黑色。RGB/RGBA 不调整显示范围。</p>
    {hasAnnotations && <label><input type="checkbox" checked={showAnnotations}
      onChange={(event) => setShowAnnotations(event.target.checked)} />显示独立标注</label>}
    {failed ? <p role="status">此成品暂时无法显示预览，仍可下载原像素文件。</p>
      : <div className="iw-preview-stage" style={{ width: Math.min(880, 400 * width / height), aspectRatio: `${width} / ${height}` }}>
        <img alt="原像素成品的显示预览" src={`/api/image/results/${id}/preview.png`}
          onError={() => setFailed(true)} />
        {hasAnnotations && showAnnotations && <img className="iw-preview-overlay" alt="独立标注预览"
          src={`/api/image/results/${id}/annotations-preview.svg?v=${revision}`} />}
      </div>}
  </section>
}
