#@ org.scijava.io.IOService ioService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def request = new JsonSlurper().parse(new File(System.getenv('BFS_FIJI_JOB_JSON') ?: ''))
def report = new File(request.output_path as String)
def payload
int exitCode = 0
try {
    def dataset = ioService.open(new File(request.input_path as String).absolutePath)
    if (!(dataset instanceof net.imagej.Dataset)) throw new IllegalArgumentException('Fiji did not return a Dataset')
    def collection = request.collection
    if (dataset.numDimensions() != collection.source.axes.size())
        throw new IllegalArgumentException('Dataset axes changed after inspection')
    for (int axis = 0; axis < dataset.numDimensions(); axis++) {
        def expected = collection.source.axes[axis]
        if (dataset.axis(axis).type().getLabel() != expected.name ||
                dataset.dimension(axis) != (expected.length as long))
            throw new IllegalArgumentException('Dataset axes changed after inspection')
    }
    def image = ij.IJ.openImage(new File(request.input_path as String).absolutePath)
    if (image == null) throw new IllegalArgumentException('ImageJ1 could not open source')
    int channels = collection.source.axes.find { it.name == 'Channel' }?.length ?: 1
    int slices = collection.source.axes.find { it.name == 'Z' }?.length ?: 1
    int frames = collection.source.axes.find { it.name == 'Time' }?.length ?: 1
    if (image.getNChannels() != channels || image.getNSlices() != slices || image.getNFrames() != frames)
        throw new IllegalArgumentException('ImageJ1 axes differ from Fiji Dataset')
    def manager = new ij.plugin.frame.RoiManager(false)
    def extras = request.extra_measurements ?: []
    int measures = ij.measure.Measurements.AREA | ij.measure.Measurements.MEAN | ij.measure.Measurements.MIN_MAX
    if (extras.contains('std_dev')) measures |= ij.measure.Measurements.STD_DEV
    if (extras.contains('median')) measures |= ij.measure.Measurements.MEDIAN
    if (extras.contains('mode')) measures |= ij.measure.Measurements.MODE
    if (extras.contains('integrated_density')) measures |= ij.measure.Measurements.INTEGRATED_DENSITY
    def rows = []
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
        int c = ((item.indices.C ?: 0) as int) + 1
        int z = ((item.indices.Z ?: 0) as int) + 1
        int t = ((item.indices.T ?: 0) as int) + 1
        roi.setName(item.name as String)
        roi.setPosition(c, z, t)
        manager.addRoi(roi)
        def nativeRoi = manager.getRoi(manager.getCount() - 1)
        image.setPosition(c, z, t)
        image.setRoi(nativeRoi)
        def table = new ij.measure.ResultsTable()
        new ij.plugin.filter.Analyzer(image, measures, table).measure()
        if (table.getCounter() != 1) throw new IllegalStateException('Analyzer produced an unexpected row count')
        def bounds = nativeRoi.getBounds()
        def mask = nativeRoi.getMask()
        long sampleCount = 0L
        for (int y = 0; y < bounds.height; y++)
            for (int x = 0; x < bounds.width; x++)
                if (mask == null || mask.getPixel(x, y) != 0) sampleCount++
        if (sampleCount < 1L || sampleCount > (region.width as long) * (region.height as long))
            throw new IllegalStateException('Native ROI pixel count differs from validated bounds')
        def values = [area: table.getValue('Area', 0),
                      area_unit: image.getCalibration().getUnit() + '^2',
                      mean: table.getValue('Mean', 0),
                      min: table.getValue('Min', 0), max: table.getValue('Max', 0)]
        if (extras.contains('std_dev')) values.std_dev = table.getValue('StdDev', 0)
        if (extras.contains('median')) values.median = table.getValue('Median', 0)
        if (extras.contains('mode')) values.mode = table.getValue('Mode', 0)
        if (extras.contains('integrated_density')) {
            values.integrated_density = table.getValue('IntDen', 0)
            values.raw_integrated_density = table.getValue('RawIntDen', 0)
        }
        if (values.any { key, value -> key != 'area_unit' && !Double.isFinite(value as double) })
            throw new IllegalArgumentException('Native ROI measurement is not finite')
        rows.add([id: item.id, name: item.name, indices: item.indices,
                  roi: region, sample_count: sampleCount, imagej1_analyzer: values])
    }
    payload = [ok: true, source: collection.source, rows: rows,
               extra_measurements: extras,
               method: 'ImageJ1 Analyzer per ROI at its explicit C/Z/T plane',
               roi_manager_multi_measure_equivalent: false]
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
