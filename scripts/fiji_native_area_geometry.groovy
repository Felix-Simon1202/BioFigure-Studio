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

    def construct
    construct = { Map region ->
        def kind = region.kind
        if (kind == 'shape_path')
            return new ij.gui.ShapeRoi(region.path.collect { it as float } as float[])
        if (kind == 'rectangle')
            return new ij.gui.Roi(region.x as double, region.y as double,
                                  region.width as double, region.height as double)
        if (kind == 'oval')
            return new ij.gui.OvalRoi(region.x as double, region.y as double,
                                      region.width as double, region.height as double)
        if (kind == 'rotated_rectangle')
            return new ij.gui.RotatedRectRoi(region.x1 as double, region.y1 as double,
                region.x2 as double, region.y2 as double, region.rect_width as double)
        if (kind == 'rotated_ellipse')
            return new ij.gui.EllipseRoi(region.x1 as double, region.y1 as double,
                region.x2 as double, region.y2 as double, region.aspect_ratio as double)
        if (kind in ['polygon', 'freehand', 'traced', 'spline_polygon']) {
            float[] xs = region.points.collect { it.x as float } as float[]
            float[] ys = region.points.collect { it.y as float } as float[]
            int type = kind == 'freehand' ? ij.gui.Roi.FREEROI :
                kind == 'traced' ? ij.gui.Roi.TRACED_ROI : ij.gui.Roi.POLYGON
            def result = new ij.gui.PolygonRoi(xs, ys, xs.length, type)
            if (kind == 'spline_polygon') result.fitSpline(region.evaluation_points as int)
            return result
        }
        if (kind == 'shape') {
            def result = new ij.gui.ShapeRoi(construct(region.operands[0] as Map))
            for (int i = 1; i < region.operands.size(); i++) {
                def next = new ij.gui.ShapeRoi(construct(region.operands[i] as Map))
                switch (region.operation) {
                    case 'union': result.or(next); break
                    case 'intersection': result.and(next); break
                    case 'xor': result.xor(next); break
                    case 'subtract': result.not(next); break
                }
            }
            return result
        }
        throw new IllegalArgumentException('Unsupported native area ROI kind')
    }
    def roi = construct(request.roi as Map)
    def floatOutline = roi.getFloatPolygon()
    if (floatOutline == null || floatOutline.npoints < 3 || floatOutline.npoints > 4096)
        throw new IllegalArgumentException('Native ROI outline is empty or exceeds limit')
    def outline = (0..<floatOutline.npoints).collect { i ->
        [x: floatOutline.xpoints[i] as double, y: floatOutline.ypoints[i] as double]
    }
    // OvalRoi's fixed polygon sampling may overshoot a requested edge by ~0.0004 px.
    if (outline.any { !Double.isFinite(it.x) || !Double.isFinite(it.y) ||
            it.x < -0.01 || it.y < -0.01 ||
            it.x > image.getWidth() + 0.01 || it.y > image.getHeight() + 0.01 })
        throw new IllegalArgumentException('Native ROI outline escapes source image: ' +
            [outline.collect { it.x }.min(), outline.collect { it.y }.min(),
             outline.collect { it.x }.max(), outline.collect { it.y }.max()])
    def bounds = roi.getBounds()
    if (bounds.width <= 0 || bounds.height <= 0 || bounds.x < 0 || bounds.y < 0 ||
            bounds.x + bounds.width > image.getWidth() || bounds.y + bounds.height > image.getHeight() ||
            bounds.width * (long)bounds.height > 1000000L)
        throw new IllegalArgumentException('Native ROI bounds escape image or exceed pixel budget')
    if (roi instanceof ij.gui.ShapeRoi && roi.getShape().getBounds2D().isEmpty())
        throw new IllegalArgumentException('Empty ShapeRoi cannot be measured')
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
    int measurements = request.measurement_bits as int
    int oldMeasurements = ij.plugin.filter.Analyzer.getMeasurements()
    int oldPrecision = ij.plugin.filter.Analyzer.getPrecision()
    def oldRedirect = ij.plugin.filter.Analyzer.isRedirectImage() ?
        ij.plugin.filter.Analyzer.getRedirectImage(image) : null
    def table = new ij.measure.ResultsTable()
    int before = image.getOverlay()?.size() ?: 0
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
    if (table.getCounter() != 1) throw new IllegalArgumentException('Native Measure returned no single row')
    def headings = []
    for (int col = 0; col <= table.getLastColumn(); col++) {
        String heading = table.getColumnHeading(col)
        if (heading != null && table.getColumn(col) != null) headings.add(heading)
    }
    def row = [:]
    def nonFinite = []
    for (String heading in headings) {
        double value = table.getValue(heading, 0)
        if (Double.isFinite(value)) row[heading] = value
        else { row[heading] = null; nonFinite.add(heading) }
    }
    def sourceCal = image.getCalibration()
    def sampledCal = sampled.getCalibration()
    def spline = roi instanceof ij.gui.PolygonRoi && roi.isSplineFit()
    def nativeParams = roi instanceof ij.gui.RotatedRectRoi || roi instanceof ij.gui.EllipseRoi ?
        (roi.getParams() as double[]).collect { it } : null
    def path = roi instanceof ij.gui.ShapeRoi ?
        (roi.getShapeAsArray() as float[]).collect { it as double } : null
    if (path != null && path.size() > 4096)
        throw new IllegalArgumentException('Native ShapeRoi path exceeds report limit')
    def floatBounds = roi.getFloatBounds()
    payload = [ok: true, source_sha256: request.source_sha256,
        redirect_sha256: redirect?.sha256, current_plane: plane, redirect_plane: redirect?.plane,
        roi: request.roi, settings: request.settings, measurement_bits: measurements,
        source_stack_index: image.getCurrentSlice(), sampled_stack_index: sampled.getCurrentSlice(),
        native_roi: [class_name: roi.getClass().getName(), type_code: roi.getType(),
                     subpixel: roi.subPixelResolution(), spline_fit: spline,
                     native_params: nativeParams,
                     bounds: [x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height],
                     float_bounds: [x: floatBounds.x, y: floatBounds.y, width: floatBounds.width, height: floatBounds.height],
                     float_outline: outline, shape_path: path],
        source_calibration: [pixel_width: sourceCal.pixelWidth, pixel_height: sourceCal.pixelHeight,
                             unit: sourceCal.getUnit(), value_unit: sourceCal.getValueUnit()],
        sampled_calibration: [pixel_width: sampledCal.pixelWidth, pixel_height: sampledCal.pixelHeight,
                              unit: sampledCal.getUnit(), value_unit: sampledCal.getValueUnit()],
        headings: headings, row: row, label: table.getLabel(0), displayed_row: table.getRowAsString(0),
        non_finite_headings: nonFinite, overlay_count_before: before,
        overlay_count: image.getOverlay()?.size() ?: 0, row_count: table.getCounter(),
        imagej1_version: ij.IJ.getVersion(), implementation: 'ImageJ1 Analyzer.run/measure']
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
