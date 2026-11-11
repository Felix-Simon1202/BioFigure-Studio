#@ org.scijava.io.IOService ioService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def request = new JsonSlurper().parse(new File(System.getenv('BFS_FIJI_JOB_JSON') ?: ''))
def report = new File(request.output_path as String)
def payload
int exitCode = 0
try {
    def dataset = ioService.open(new File(request.input_path as String).absolutePath)
    if (!(dataset instanceof net.imagej.Dataset) || dataset.numDimensions() != request.source_axes.size())
        throw new IllegalArgumentException('Source is not the inspected Dataset')
    for (int axis = 0; axis < dataset.numDimensions(); axis++) {
        def expected = request.source_axes[axis]
        if (dataset.axis(axis).type().getLabel() != expected.name ||
                dataset.dimension(axis) != (expected.length as long))
            throw new IllegalArgumentException('Source axes changed after inspection')
    }
    def image = ij.IJ.openImage(new File(request.input_path as String).absolutePath)
    if (image == null) throw new IllegalArgumentException('ImageJ1 could not open source')
    int channels = request.source_axes.find { it.name == 'Channel' }?.length ?: 1
    int slices = request.source_axes.find { it.name == 'Z' }?.length ?: 1
    int frames = request.source_axes.find { it.name == 'Time' }?.length ?: 1
    if (image.getNChannels() != channels || image.getNSlices() != slices || image.getNFrames() != frames)
        throw new IllegalArgumentException('ImageJ1 source axes differ from Fiji Dataset')
    def plane = request.current_plane
    image.setPosition(((plane.C ?: 0) as int) + 1, ((plane.Z ?: 0) as int) + 1,
                      ((plane.T ?: 0) as int) + 1)
    def region = request.roi
    float[] xs = region.points.collect { it.x as float } as float[]
    float[] ys = region.points.collect { it.y as float } as float[]
    def roi
    if (region.kind == 'line')
        roi = new ij.gui.Line(region.points[0].x as double, region.points[0].y as double,
                              region.points[1].x as double, region.points[1].y as double)
    else if (region.kind == 'polyline' || region.kind == 'freeline' || region.kind == 'angle') {
        int type = region.kind == 'polyline' ? ij.gui.Roi.POLYLINE :
                   region.kind == 'freeline' ? ij.gui.Roi.FREELINE : ij.gui.Roi.ANGLE
        roi = new ij.gui.PolygonRoi(xs, ys, xs.length, type)
    } else if (region.kind == 'point' || region.kind == 'multipoint') {
        roi = new ij.gui.PointRoi(xs, ys, xs.length)
        int[] counters = (0..<xs.length).collect { index ->
            ((region.point_positions[index] as int) << 8) | (region.point_counters[index] as int)
        } as int[]
        roi.setCounters(counters)
    } else throw new IllegalArgumentException('Unsupported non-area ROI type')
    if (region.kind in ['line', 'polyline', 'freeline'])
        roi.setStrokeWidth(region.stroke_width as float)
    image.setRoi(roi)
    def redirect = request.redirect
    def target = null
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
        if (target == null || target.getWidth() != image.getWidth() || target.getHeight() != image.getHeight())
            throw new IllegalArgumentException('Redirect dimensions differ')
        int tc = redirect.axes.find { it.name == 'Channel' }?.length ?: 1
        int tz = redirect.axes.find { it.name == 'Z' }?.length ?: 1
        int tt = redirect.axes.find { it.name == 'Time' }?.length ?: 1
        if (target.getNChannels() != tc || target.getNSlices() != tz || target.getNFrames() != tt)
            throw new IllegalArgumentException('ImageJ1 redirect axes differ from Fiji Dataset')
        target.setPosition(((redirect.plane.C ?: 0) as int) + 1,
                           ((redirect.plane.Z ?: 0) as int) + 1,
                           ((redirect.plane.T ?: 0) as int) + 1)
        if (target.getStackSize() > 1 && target.getCurrentSlice() != image.getCurrentSlice())
            throw new IllegalArgumentException('Redirect linear position differs')
    }
    def sampled = target ?: image
    if (request.settings.threshold != null)
        sampled.getProcessor().setThreshold(request.settings.threshold.min as double,
            request.settings.threshold.max as double, ij.process.ImageProcessor.NO_LUT_UPDATE)
    def bits = [
        area: ij.measure.Measurements.AREA, mean: ij.measure.Measurements.MEAN,
        std_dev: ij.measure.Measurements.STD_DEV, mode: ij.measure.Measurements.MODE,
        min_max: ij.measure.Measurements.MIN_MAX, centroid: ij.measure.Measurements.CENTROID,
        center_of_mass: ij.measure.Measurements.CENTER_OF_MASS,
        perimeter: ij.measure.Measurements.PERIMETER,
        bounding_rectangle: ij.measure.Measurements.RECT,
        fit_ellipse: ij.measure.Measurements.ELLIPSE,
        shape_descriptors: ij.measure.Measurements.SHAPE_DESCRIPTORS,
        feret: ij.measure.Measurements.FERET,
        integrated_density: ij.measure.Measurements.INTEGRATED_DENSITY,
        median: ij.measure.Measurements.MEDIAN, skewness: ij.measure.Measurements.SKEWNESS,
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
    for (String option in request.settings.measurements) measurements |= bits[option] as int
    int oldMeasurements = ij.plugin.filter.Analyzer.getMeasurements()
    int oldPrecision = ij.plugin.filter.Analyzer.getPrecision()
    def oldRedirect = ij.plugin.filter.Analyzer.isRedirectImage()
        ? ij.plugin.filter.Analyzer.getRedirectImage(image) : null
    int overlayBefore = image.getOverlay()?.size() ?: 0
    def table = new ij.measure.ResultsTable()
    try {
        ij.plugin.filter.Analyzer.setMeasurements(measurements)
        ij.plugin.filter.Analyzer.setPrecision(request.settings.decimal_places as int)
        ij.plugin.filter.Analyzer.setRedirectImage(target)
        def analyzer = new ij.plugin.filter.Analyzer(image, measurements, table)
        if (request.settings.measurements.contains('add_to_overlay')) analyzer.run(image.getProcessor())
        else analyzer.measure()
    } finally {
        ij.plugin.filter.Analyzer.setRedirectImage(oldRedirect)
        ij.plugin.filter.Analyzer.setPrecision(oldPrecision)
        ij.plugin.filter.Analyzer.setMeasurements(oldMeasurements)
    }
    def headings = []
    for (int col = 0; col <= table.getLastColumn(); col++) {
        String heading = table.getColumnHeading(col)
        if (heading != null && table.getColumn(col) != null) headings.add(heading)
    }
    def rows = []
    def nonFinite = []
    def labels = []
    def displayedRows = []
    for (int index = 0; index < table.getCounter(); index++) {
        def values = [:]
        def invalid = []
        for (String heading in headings) {
            double value = table.getValue(heading, index)
            if (Double.isFinite(value)) values[heading] = value
            else { values[heading] = null; invalid.add(heading) }
        }
        rows.add(values)
        nonFinite.add(invalid)
        labels.add(table.getLabel(index))
        displayedRows.add(table.getRowAsString(index))
    }
    def actualPoints
    if (roi instanceof ij.gui.Line)
        actualPoints = [[x: roi.x1d, y: roi.y1d], [x: roi.x2d, y: roi.y2d]]
    else {
        def polygon = roi.getFloatPolygon()
        actualPoints = (0..<polygon.npoints).collect { index ->
            [x: polygon.xpoints[index] as double, y: polygon.ypoints[index] as double]
        }
    }
    def bounds = roi.getBounds()
    def sourceCal = image.getCalibration()
    def sampledCal = sampled.getCalibration()
    payload = [ok: true, source_sha256: request.source_sha256,
        redirect_sha256: redirect?.sha256, current_plane: plane,
        redirect_plane: redirect?.plane, roi: region, settings: request.settings,
        measurement_bits: measurements, source_stack_index: image.getCurrentSlice(),
        sampled_stack_index: sampled.getCurrentSlice(),
        native_roi: [points: actualPoints, class_name: roi.getClass().getName(), type_code: roi.getType(),
                     stroke_width: roi.getStrokeWidth(), subpixel: roi.subPixelResolution(),
                     bounds: [x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height],
                     point_positions: roi instanceof ij.gui.PointRoi ?
                         (0..<xs.length).collect { roi.getPointPosition(it) } : null,
                     point_counters: roi instanceof ij.gui.PointRoi ?
                         (roi.getCounters() as int[]).collect { it & 0xff } : null],
        source_calibration: [pixel_width: sourceCal.pixelWidth, pixel_height: sourceCal.pixelHeight,
                             unit: sourceCal.getUnit(), value_unit: sourceCal.getValueUnit()],
        sampled_calibration: [pixel_width: sampledCal.pixelWidth, pixel_height: sampledCal.pixelHeight,
                              unit: sampledCal.getUnit(), value_unit: sampledCal.getValueUnit()],
        headings: headings, rows: rows, labels: labels, displayed_rows: displayedRows,
        non_finite_headings: nonFinite,
        overlay_count_before: overlayBefore, overlay_count: image.getOverlay()?.size() ?: 0, row_count: table.getCounter(),
        imagej1_version: ij.IJ.getVersion(), implementation: 'ImageJ1 Analyzer.run/measure']
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
