#@ org.scijava.io.IOService ioService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def request = new JsonSlurper().parse(new File(System.getenv('BFS_FIJI_JOB_JSON') ?: ''))
def report = new File(request.output_path as String)
def payload
int exitCode = 0
try {
    def selection = request.selection
    def settings = request.settings
    def sourceDataset = ioService.open(new File(request.input_path as String).absolutePath)
    if (!(sourceDataset instanceof net.imagej.Dataset) || sourceDataset.numDimensions() != selection.source_axes.size())
        throw new IllegalArgumentException('Source is not the inspected Dataset')
    for (int axis = 0; axis < sourceDataset.numDimensions(); axis++) {
        def expected = selection.source_axes[axis]
        if (sourceDataset.axis(axis).type().getLabel() != expected.name ||
                sourceDataset.dimension(axis) != (expected.length as long))
            throw new IllegalArgumentException('Source axes changed after inspection')
    }
    def source = ij.IJ.openImage(new File(request.input_path as String).absolutePath)
    if (source == null) throw new IllegalArgumentException('ImageJ1 could not open source')
    int sourceChannels = selection.source_axes.find { it.name == 'Channel' }?.length ?: 1
    int sourceSlices = selection.source_axes.find { it.name == 'Z' }?.length ?: 1
    int sourceFrames = selection.source_axes.find { it.name == 'Time' }?.length ?: 1
    if (source.getNChannels() != sourceChannels || source.getNSlices() != sourceSlices ||
            source.getNFrames() != sourceFrames)
        throw new IllegalArgumentException('ImageJ1 source axes differ from inspected Fiji Dataset')
    source.setPosition(((selection.indices.C ?: 0) as int) + 1,
                       ((selection.indices.Z ?: 0) as int) + 1,
                       ((selection.indices.T ?: 0) as int) + 1)
    def region = selection.roi
    def roi
    if (region.kind == 'rectangle' || region.kind == 'full')
        roi = new ij.gui.Roi(region.x as int, region.y as int, region.width as int, region.height as int)
    else if (region.kind == 'ellipse')
        roi = new ij.gui.OvalRoi(region.x as int, region.y as int, region.width as int, region.height as int)
    else if (region.kind == 'polygon') {
        int[] xs = region.points.collect { it.x as int } as int[]
        int[] ys = region.points.collect { it.y as int } as int[]
        roi = new ij.gui.PolygonRoi(xs, ys, xs.length, ij.gui.Roi.POLYGON)
    } else throw new IllegalArgumentException('Unsupported ROI kind')
    source.setRoi(roi)

    def target = null
    def redirect = request.redirect
    if (redirect != null) {
        def targetDataset = ioService.open(new File(redirect.path as String).absolutePath)
        if (!(targetDataset instanceof net.imagej.Dataset) || targetDataset.numDimensions() != redirect.axes.size())
            throw new IllegalArgumentException('Redirect is not the inspected Dataset')
        for (int axis = 0; axis < targetDataset.numDimensions(); axis++) {
            def expected = redirect.axes[axis]
            if (targetDataset.axis(axis).type().getLabel() != expected.name ||
                    targetDataset.dimension(axis) != (expected.length as long))
                throw new IllegalArgumentException('Redirect axes changed after inspection')
        }
        target = ij.IJ.openImage(new File(redirect.path as String).absolutePath)
        if (target == null || target.getWidth() != source.getWidth() || target.getHeight() != source.getHeight())
            throw new IllegalArgumentException('Redirect X/Y dimensions differ')
        int targetChannels = redirect.axes.find { it.name == 'Channel' }?.length ?: 1
        int targetSlices = redirect.axes.find { it.name == 'Z' }?.length ?: 1
        int targetFrames = redirect.axes.find { it.name == 'Time' }?.length ?: 1
        if (target.getNChannels() != targetChannels || target.getNSlices() != targetSlices ||
                target.getNFrames() != targetFrames)
            throw new IllegalArgumentException('ImageJ1 redirect axes differ from inspected Fiji Dataset')
        target.setPosition(((redirect.plane.C ?: 0) as int) + 1,
                           ((redirect.plane.Z ?: 0) as int) + 1,
                           ((redirect.plane.T ?: 0) as int) + 1)
        if (target.getStackSize() > 1 && target.getCurrentSlice() != source.getCurrentSlice())
            throw new IllegalArgumentException('Redirect linear stack position differs')
    }
    def sampled = target ?: source
    def threshold = settings.threshold
    if (threshold != null)
        sampled.getProcessor().setThreshold(threshold.min as double, threshold.max as double,
                                             ij.process.ImageProcessor.NO_LUT_UPDATE)
    def bits = [
        area: ij.measure.Measurements.AREA, mean: ij.measure.Measurements.MEAN,
        std_dev: ij.measure.Measurements.STD_DEV, mode: ij.measure.Measurements.MODE,
        min_max: ij.measure.Measurements.MIN_MAX, centroid: ij.measure.Measurements.CENTROID,
        center_of_mass: ij.measure.Measurements.CENTER_OF_MASS,
        perimeter: ij.measure.Measurements.PERIMETER, bounding_rectangle: ij.measure.Measurements.RECT,
        fit_ellipse: ij.measure.Measurements.ELLIPSE,
        shape_descriptors: ij.measure.Measurements.SHAPE_DESCRIPTORS,
        feret: ij.measure.Measurements.FERET,
        integrated_density: ij.measure.Measurements.INTEGRATED_DENSITY,
        median: ij.measure.Measurements.MEDIAN,
        skewness: ij.measure.Measurements.SKEWNESS,
        kurtosis: ij.measure.Measurements.KURTOSIS,
        area_fraction: ij.measure.Measurements.AREA_FRACTION,
        stack_position: ij.measure.Measurements.STACK_POSITION,
        limit_to_threshold: ij.measure.Measurements.LIMIT,
        display_label: ij.measure.Measurements.LABELS,
        invert_y: ij.measure.Measurements.INVERT_Y,
        scientific_notation: ij.measure.Measurements.SCIENTIFIC_NOTATION,
        add_to_overlay: ij.measure.Measurements.ADD_TO_OVERLAY,
        nan_empty_cells: ij.measure.Measurements.NaN_EMPTY_CELLS,
    ]
    int measurements = 0
    for (String option : settings.measurements) measurements |= bits[option] as int
    int oldMeasurements = ij.plugin.filter.Analyzer.getMeasurements()
    int oldPrecision = ij.plugin.filter.Analyzer.getPrecision()
    def oldRedirect = ij.plugin.filter.Analyzer.isRedirectImage()
        ? ij.plugin.filter.Analyzer.getRedirectImage(source) : null
    int overlayBefore = source.getOverlay()?.size() ?: 0
    def table = new ij.measure.ResultsTable()
    try {
        ij.plugin.filter.Analyzer.setMeasurements(measurements)
        ij.plugin.filter.Analyzer.setPrecision(settings.decimal_places as int)
        ij.plugin.filter.Analyzer.setRedirectImage(target)
        def analyzer = new ij.plugin.filter.Analyzer(source, measurements, table)
        if (settings.measurements.contains('add_to_overlay')) analyzer.run(source.getProcessor())
        else analyzer.measure()
    } finally {
        ij.plugin.filter.Analyzer.setRedirectImage(oldRedirect)
        ij.plugin.filter.Analyzer.setPrecision(oldPrecision)
        ij.plugin.filter.Analyzer.setMeasurements(oldMeasurements)
    }
    if (table.getCounter() != 1) throw new IllegalStateException('Native Analyzer did not produce one row')
    def headings = []
    def row = [:]
    def nonFinite = []
    for (int col = 0; col <= table.getLastColumn(); col++) {
        String heading = table.getColumnHeading(col)
        if (heading == null || table.getColumn(col) == null) continue
        headings.add(heading)
        double value = table.getValue(heading, 0)
        if (Double.isFinite(value)) row[heading] = value
        else { row[heading] = null; nonFinite.add(heading) }
    }
    def cal = sampled.getCalibration()
    def sourceCal = source.getCalibration()
    payload = [ok: true, source_sha256: request.source_sha256,
        redirect_sha256: redirect?.sha256, redirect_plane: redirect?.plane,
        selection: selection, settings: settings, measurement_bits: measurements,
        source_stack_index: source.getCurrentSlice(),
        sampled_stack_index: sampled.getCurrentSlice(),
        sampled_calibration: [pixel_width: cal.pixelWidth, pixel_height: cal.pixelHeight,
                              unit: cal.getUnit(), value_unit: cal.getValueUnit(),
                              calibrated_density: cal.calibrated()],
        roi_source_calibration: [pixel_width: sourceCal.pixelWidth,
                                 pixel_height: sourceCal.pixelHeight,
                                 unit: sourceCal.getUnit(), value_unit: sourceCal.getValueUnit(),
                                 calibrated_density: sourceCal.calibrated()],
        headings: headings, row: row, non_finite_headings: nonFinite,
        label: table.getLabel(0), displayed_row: table.getRowAsString(0),
        overlay_count_before: overlayBefore, overlay_count: source.getOverlay()?.size() ?: 0, row_count: table.getCounter(),
        imagej1_version: ij.IJ.getVersion(), implementation: 'ImageJ1 Analyzer.run/measure']
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
