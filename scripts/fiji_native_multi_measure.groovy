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
    def plane = request.current_plane
    image.setPosition(((plane.C ?: 0) as int) + 1, ((plane.Z ?: 0) as int) + 1,
                      ((plane.T ?: 0) as int) + 1)
    int currentSlice = image.getCurrentSlice()
    def manager = new ij.plugin.frame.RoiManager(false)
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
        } else throw new IllegalArgumentException('Unsupported ROI type')
        roi.setName(item.name as String)
        roi.setPosition(((item.indices.C ?: 0) as int) + 1,
                        ((item.indices.Z ?: 0) as int) + 1,
                        ((item.indices.T ?: 0) as int) + 1)
        manager.addRoi(roi)
    }
    if (manager.getCount() != collection.items.size()) throw new IllegalStateException('ROI Manager count differs')
    for (int index = 0; index < manager.getCount(); index++)
        if (manager.getName(index) != collection.items[index].name)
            throw new IllegalStateException('ROI Manager name differs from collection')
    int originalMeasurements = ij.plugin.filter.Analyzer.getMeasurements()
    int measurements = ij.measure.Measurements.AREA | ij.measure.Measurements.MEAN | ij.measure.Measurements.MIN_MAX
    def extras = request.measurement_flags ?: []
    if (extras.contains('std_dev')) measurements |= ij.measure.Measurements.STD_DEV
    if (extras.contains('median')) measurements |= ij.measure.Measurements.MEDIAN
    if (extras.contains('mode')) measurements |= ij.measure.Measurements.MODE
    if (extras.contains('integrated_density')) measurements |= ij.measure.Measurements.INTEGRATED_DENSITY
    def macroField = ij.IJ.class.getDeclaredField('macroRunning')
    macroField.setAccessible(true)
    boolean originalMacro = macroField.getBoolean(null)
    def rowPerSliceField = ij.plugin.frame.RoiManager.class.getDeclaredField('mmResults')
    def rowPerRoiField = ij.plugin.frame.RoiManager.class.getDeclaredField('mmResults2')
    rowPerSliceField.setAccessible(true)
    rowPerRoiField.setAccessible(true)
    ij.plugin.frame.RoiManager.resetMultiMeasureResults()
    def tables = []
    def previousCounts = [one_row_per_slice: 0, one_row_per_measurement: 0]
    try {
        ij.plugin.filter.Analyzer.setMeasurements(measurements)
        for (run in request.runs) {
            macroField.setBoolean(null, true)
            if (!ij.IJ.isMacro()) throw new IllegalStateException('ImageJ1 macro mode unavailable')
            image.setSlice(currentSlice)
            String command = 'multi-measure'
            if (run.measure_all) command += ' measure_all'
            if (run.one_row_per_slice) command += ' one'
            if (run.append_results) command += ' append'
            if (!manager.runCommand(image, command)) throw new IllegalStateException('Native Multi Measure command failed')
            def table = run.one_row_per_slice ? rowPerSliceField.get(null) : rowPerRoiField.get(null)
            if (table == null) throw new IllegalStateException('Native Multi Measure table missing')
            def headings = []
            for (int col = 0; col <= table.getLastColumn(); col++) {
                String heading = table.getColumnHeading(col)
                if (heading != null && table.getColumn(col) != null) headings.add(heading)
            }
            def values = (0..<table.getCounter()).collect { row ->
                headings.collectEntries { heading -> [(heading): table.getValue(heading, row)] }
            }
            String layout = run.one_row_per_slice ? 'one_row_per_slice' : 'one_row_per_measurement'
            int previous = run.append_results ? previousCounts[layout] : 0
            tables.add([options: run, layout: layout, headings: headings, rows: values,
                        row_count: table.getCounter(), new_row_start: previous,
                        new_row_count: table.getCounter() - previous])
            previousCounts[layout] = table.getCounter()
        }
    } finally {
        macroField.setBoolean(null, originalMacro)
        ij.plugin.filter.Analyzer.setMeasurements(originalMeasurements)
        ij.plugin.frame.RoiManager.resetMultiMeasureResults()
    }
    def planes = (1..image.getStackSize()).collect { stackIndex ->
        int[] czt = image.convertIndexToPosition(stackIndex)
        [stack_index: stackIndex, C: czt[0] - 1, Z: czt[1] - 1, T: czt[2] - 1]
    }
    payload = [ok: true, source: collection.source,
               roi_order: collection.items.collect { item -> [id: item.id, name: item.name,
                    saved_indices: item.indices, roi: item.roi] },
               current_plane: plane, current_stack_index: currentSlice,
               stack_planes: planes, measurement_flags: extras, runs: tables,
               imagej1_version: ij.IJ.getVersion(),
               implementation: 'ImageJ1 RoiManager.runCommand multi-measure']
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
