#@ org.scijava.io.IOService ioService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def request = new JsonSlurper().parse(new File(System.getenv('BFS_FIJI_JOB_JSON') ?: ''))
def report = new File(request.output_path as String)
def archive = new File(report.parentFile, 'native-rois.zip')
def payload
int exitCode = 0
try {
    def dataset = ioService.open(new File(request.input_path as String).absolutePath)
    if (!(dataset instanceof net.imagej.Dataset)) throw new IllegalArgumentException('Fiji did not return a Dataset')
    def image = ij.IJ.openImage(new File(request.input_path as String).absolutePath)
    if (image == null) throw new IllegalArgumentException('ImageJ1 could not open source')
    def manager = new ij.plugin.frame.RoiManager(false)
    if (request.operation == 'export') {
        def collection = request.collection
        if (collection.items.isEmpty() || collection.items.size() > 64) throw new IllegalArgumentException('ROI count outside export range')
        for (item in collection.items) {
            def region = item.roi
            def roi
            if (region.kind == 'rectangle')
                roi = new ij.gui.Roi(region.x as int, region.y as int, region.width as int, region.height as int)
            else if (region.kind == 'ellipse')
                roi = new ij.gui.OvalRoi(region.x as int, region.y as int, region.width as int, region.height as int)
            else if (region.kind == 'polygon') {
                int[] xs = region.points.collect { it.x as int } as int[]
                int[] ys = region.points.collect { it.y as int } as int[]
                roi = new ij.gui.PolygonRoi(xs, ys, xs.length, ij.gui.Roi.POLYGON)
            } else throw new IllegalArgumentException('Unsupported ROI kind')
            roi.setName(item.name as String)
            roi.setPosition(((item.indices.C ?: 0) as int) + 1,
                            ((item.indices.Z ?: 0) as int) + 1,
                            ((item.indices.T ?: 0) as int) + 1)
            manager.addRoi(roi)
        }
        if (!manager.runCommand('Save', archive.absolutePath)) throw new IllegalStateException('Native ROI ZIP save failed')
        if (archive.length() > 524288L) throw new IllegalArgumentException('Native ROI ZIP exceeds 512 KiB')
        payload = [ok: true, archive_base64: archive.bytes.encodeBase64().toString(), count: manager.getCount()]
    } else if (request.operation == 'import') {
        archive.bytes = (request.archive_base64 as String).decodeBase64()
        if (!manager.runCommand('Open', archive.absolutePath)) throw new IllegalArgumentException('Native ROI ZIP open failed')
        if (manager.getCount() != (request.roi_count as int)) throw new IllegalArgumentException('Native ROI entry count changed')
        def items = []
        def measured = []
        for (int index = 0; index < manager.getCount(); index++) {
            def roi = manager.getRoi(index)
            String kind
            def region
            if (roi.getType() == ij.gui.Roi.RECTANGLE) kind = 'rectangle'
            else if (roi.getType() == ij.gui.Roi.OVAL) kind = 'ellipse'
            else if (roi.getType() == ij.gui.Roi.POLYGON) kind = 'polygon'
            else throw new IllegalArgumentException('Unsupported native ROI type: ' + roi.getType())
            def precise = roi.getFloatBounds()
            if ([precise.x, precise.y, precise.width, precise.height].any {
                !Double.isFinite(it as double) || (it as double) != Math.rint(it as double) })
                throw new IllegalArgumentException('Native ROI has fractional bounds')
            def bounds = roi.getBounds()
            if (kind == 'polygon') {
                def floating = roi.getFloatPolygon()
                if ((0..<floating.npoints).any { i ->
                    floating.xpoints[i] != Math.rint(floating.xpoints[i] as double) ||
                    floating.ypoints[i] != Math.rint(floating.ypoints[i] as double) })
                    throw new IllegalArgumentException('Native polygon has fractional vertices')
                def poly = roi.getPolygon()
                region = [kind: kind, points: (0..<poly.npoints).collect { i ->
                    [x: poly.xpoints[i], y: poly.ypoints[i]] }]
            } else {
                def pixels = [bounds.x, bounds.y, bounds.width, bounds.height]
                if (pixels.any { !Double.isFinite(it as double) || (it as double) != Math.rint(it as double) })
                    throw new IllegalArgumentException('Native ROI has fractional bounds')
                region = [kind: kind, x: bounds.x as int, y: bounds.y as int,
                          width: bounds.width as int, height: bounds.height as int]
            }
            int c = roi.getCPosition()
            int z = roi.getZPosition()
            int t = roi.getTPosition()
            if ((image.getNChannels()>1 && c<1) || (image.getNSlices()>1 && z<1) ||
                    (image.getNFrames()>1 && t<1)) throw new IllegalArgumentException('Native ROI lacks explicit C/Z/T position')
            def indices = [:]
            if (image.getNChannels()>1) indices.C = c-1
            if (image.getNSlices()>1) indices.Z = z-1
            if (image.getNFrames()>1) indices.T = t-1
            String name = manager.getName(index)
            if (name == null || name.isEmpty()) throw new IllegalArgumentException('Native ROI name missing')
            image.setPosition(Math.max(c,1), Math.max(z,1), Math.max(t,1))
            image.setRoi(roi)
            def table = new ij.measure.ResultsTable()
            new ij.plugin.filter.Analyzer(image,
                    ij.measure.Measurements.AREA | ij.measure.Measurements.MEAN, table).measure()
            if (table.getCounter()!=1) throw new IllegalStateException('Native ROI Measure failed')
            items.add([id: java.util.UUID.randomUUID().toString().replace('-', ''),
                       name: name, indices: indices, roi: region])
            measured.add([name: name, kind: kind, indices: indices,
                          area: table.getValue('Area', 0), mean: table.getValue('Mean', 0)])
        }
        payload = [ok: true, items: items, measurements: measured]
    } else throw new IllegalArgumentException('Unknown ROI ZIP operation')
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
} finally {
    archive.delete()
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
