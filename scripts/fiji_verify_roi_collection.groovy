#@ org.scijava.io.IOService ioService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def request = new JsonSlurper().parse(new File(System.getenv('BFS_FIJI_JOB_JSON') ?: ''))
def report = new File(request.output_path as String)
def archive = new File(report.parentFile, 'rois.zip')
def payload
int exitCode = 0
try {
    def dataset = ioService.open(new File(request.input_path as String).absolutePath)
    if (!(dataset instanceof net.imagej.Dataset)) throw new IllegalArgumentException('Fiji did not return a Dataset')
    def imagePlus = ij.IJ.openImage(new File(request.input_path as String).absolutePath)
    if (imagePlus == null) throw new IllegalArgumentException('ImageJ1 could not open source')
    def collection = request.collection
    if (dataset.numDimensions() != collection.source.axes.size()) {
        throw new IllegalArgumentException('Dataset axes differ from ROI collection')
    }
    for (int axis = 0; axis < dataset.numDimensions(); axis++) {
        def expected = collection.source.axes[axis]
        if (dataset.axis(axis).type().getLabel() != expected.name ||
                dataset.dimension(axis) != (expected.length as long)) {
            throw new IllegalArgumentException('Dataset axes differ from ROI collection')
        }
    }
    def manager = new ij.plugin.frame.RoiManager(false)
    for (item in collection.items) {
        def region = item.roi
        def roi
        if (region.kind == 'polygon') {
            int[] xs = region.points.collect { it.x as int } as int[]
            int[] ys = region.points.collect { it.y as int } as int[]
            roi = new ij.gui.PolygonRoi(xs, ys, xs.length, ij.gui.Roi.POLYGON)
        } else if (region.kind == 'ellipse') {
            roi = new ij.gui.OvalRoi(region.x as int, region.y as int,
                                     region.width as int, region.height as int)
        } else if (region.kind == 'rectangle') {
            roi = new ij.gui.Roi(region.x as int, region.y as int,
                                 region.width as int, region.height as int)
        } else {
            throw new IllegalArgumentException('Unsupported ROI kind')
        }
        roi.setName(item.name as String)
        roi.setPosition(((item.indices.C ?: 0) as int) + 1,
                        ((item.indices.Z ?: 0) as int) + 1,
                        ((item.indices.T ?: 0) as int) + 1)
        manager.addRoi(roi)
    }
    if (manager.getCount() != collection.items.size()) throw new IllegalStateException('ROI Manager add mismatch')
    if (!collection.items.isEmpty()) {
        if (!manager.runCommand('Save', archive.absolutePath)) throw new IllegalStateException('ROI Manager save failed')
        manager.reset()
        if (!manager.runCommand('Open', archive.absolutePath)) throw new IllegalStateException('ROI Manager open failed')
    }
    if (manager.getCount() != collection.items.size()) throw new IllegalStateException('ROI Manager reload count mismatch')
    def measured = []
    for (int index = 0; index < collection.items.size(); index++) {
        def item = collection.items[index]
        def roi = manager.getRoi(index)
        int c = ((item.indices.C ?: 0) as int) + 1
        int z = ((item.indices.Z ?: 0) as int) + 1
        int t = ((item.indices.T ?: 0) as int) + 1
        int expectedType = item.roi.kind == 'ellipse' ? ij.gui.Roi.OVAL :
                item.roi.kind == 'polygon' ? ij.gui.Roi.POLYGON : ij.gui.Roi.RECTANGLE
        if (roi.getName() != item.name || roi.getCPosition() != c ||
                roi.getZPosition() != z || roi.getTPosition() != t || roi.getType() != expectedType) {
            throw new IllegalStateException('ROI Manager name, type or C/Z/T changed after reload')
        }
        imagePlus.setPosition(c, z, t)
        imagePlus.setRoi(roi)
        def table = new ij.measure.ResultsTable()
        new ij.plugin.filter.Analyzer(imagePlus,
                ij.measure.Measurements.AREA | ij.measure.Measurements.MEAN, table).measure()
        if (table.getCounter() != 1) throw new IllegalStateException('Analyzer did not measure ROI')
        measured.add([name: roi.getName(), indices: item.indices,
                      kind: item.roi.kind, area: table.getValue('Area', 0),
                      mean: table.getValue('Mean', 0)])
    }
    payload = [ok: true, count: measured.size(), measurements: measured]
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
} finally {
    archive.delete()
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
