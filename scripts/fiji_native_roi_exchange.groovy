#@ org.scijava.io.IOService ioService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

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

    def construct
    construct = { Map region ->
        def kind = region.kind
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
        if (kind in ['polygon', 'freehand', 'traced', 'spline_polygon',
                     'polyline', 'freeline', 'angle']) {
            float[] xs = region.points.collect { it.x as float } as float[]
            float[] ys = region.points.collect { it.y as float } as float[]
            int type = [polygon:ij.gui.Roi.POLYGON, freehand:ij.gui.Roi.FREEROI,
                        traced:ij.gui.Roi.TRACED_ROI, spline_polygon:ij.gui.Roi.POLYGON,
                        polyline:ij.gui.Roi.POLYLINE, freeline:ij.gui.Roi.FREELINE,
                        angle:ij.gui.Roi.ANGLE][kind] as int
            def result = new ij.gui.PolygonRoi(xs, ys, xs.length, type)
            if (kind == 'spline_polygon') result.fitSpline(region.evaluation_points as int)
            if (kind in ['polyline', 'freeline']) result.setStrokeWidth(region.stroke_width as float)
            return result
        }
        if (kind == 'line') {
            def result = new ij.gui.Line(region.points[0].x as double, region.points[0].y as double,
                                         region.points[1].x as double, region.points[1].y as double)
            result.setStrokeWidth(region.stroke_width as float)
            return result
        }
        if (kind in ['point', 'multipoint']) {
            float[] xs = region.points.collect { it.x as float } as float[]
            float[] ys = region.points.collect { it.y as float } as float[]
            def result = new ij.gui.PointRoi(xs, ys, xs.length)
            int[] counters = (0..<xs.length).collect { i ->
                ((region.point_positions[i] as int) << 8) | (region.point_counters[i] as int)
            } as int[]
            result.setCounters(counters)
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
        if (kind == 'shape_path')
            return new ij.gui.ShapeRoi(region.path.collect { it as float } as float[])
        throw new IllegalArgumentException('Unsupported ROI type')
    }

    def describe = { ij.gui.Roi roi ->
        def region
        def points = { ij.process.FloatPolygon polygon ->
            (0..<polygon.npoints).collect { i ->
                [x: polygon.xpoints[i] as double, y: polygon.ypoints[i] as double]
            }
        }
        if (roi instanceof ij.gui.ShapeRoi) {
            region = [version:'1.0', kind:'shape_path',
                      path:(roi.getShapeAsArray() as float[]).collect { it as double }]
        } else if (roi instanceof ij.gui.RotatedRectRoi || roi instanceof ij.gui.EllipseRoi) {
            def params = roi.getParams() as double[]
            String kind = roi instanceof ij.gui.RotatedRectRoi ? 'rotated_rectangle' : 'rotated_ellipse'
            region = [version:'1.0', kind:kind, x1:params[0], y1:params[1],
                      x2:params[2], y2:params[3]]
            region[kind == 'rotated_rectangle' ? 'rect_width' : 'aspect_ratio'] = params[4]
        } else if (roi instanceof ij.gui.PointRoi) {
            def polygon = roi.getFloatPolygon()
            region = [version:'1.0', kind:polygon.npoints == 1 ? 'point' : 'multipoint',
                      points:points(polygon),
                      point_positions:(0..<polygon.npoints).collect { roi.getPointPosition(it) },
                      point_counters:(roi.getCounters() as int[]).toList().take(polygon.npoints).collect { it & 0xff }]
        } else if (roi instanceof ij.gui.Line) {
            region = [version:'1.0', kind:'line',
                      points:[[x:roi.x1d, y:roi.y1d], [x:roi.x2d, y:roi.y2d]],
                      stroke_width:roi.getStrokeWidth() as double]
        } else if (roi instanceof ij.gui.PolygonRoi) {
            int type = roi.getType()
            String kind = roi.isSplineFit() ? 'spline_polygon' :
                [(ij.gui.Roi.POLYGON):'polygon', (ij.gui.Roi.FREEROI):'freehand',
                 (ij.gui.Roi.TRACED_ROI):'traced', (ij.gui.Roi.POLYLINE):'polyline',
                 (ij.gui.Roi.FREELINE):'freeline', (ij.gui.Roi.ANGLE):'angle'][type]
            if (kind == null) throw new IllegalArgumentException('Unsupported decoded polygon type')
            def polygon = roi.isSplineFit() ? roi.getNonSplineFloatPolygon() : roi.getFloatPolygon()
            region = [version:'1.0', kind:kind, points:points(polygon)]
            if (kind == 'spline_polygon') region.evaluation_points = roi.getFloatPolygon().npoints
            if (kind in ['polyline', 'freeline']) region.stroke_width = roi.getStrokeWidth() as double
        } else if (roi instanceof ij.gui.OvalRoi || roi.getClass() == ij.gui.Roi) {
            def bounds = roi.getFloatBounds()
            region = [version:'1.0', kind:roi instanceof ij.gui.OvalRoi ? 'oval' : 'rectangle',
                      x:bounds.x, y:bounds.y, width:bounds.width, height:bounds.height]
        } else throw new IllegalArgumentException('Unsupported decoded ROI class: ' + roi.getClass().name)
        def indices = [:]
        if (request.source_axes.any { it.name == 'Channel' }) {
            if (roi.getCPosition() < 1) throw new IllegalArgumentException('ROI lacks C position')
            indices.C = roi.getCPosition() - 1
        }
        if (request.source_axes.any { it.name == 'Z' }) {
            if (roi.getZPosition() < 1) throw new IllegalArgumentException('ROI lacks Z position')
            indices.Z = roi.getZPosition() - 1
        }
        if (request.source_axes.any { it.name == 'Time' }) {
            if (roi.getTPosition() < 1) throw new IllegalArgumentException('ROI lacks T position')
            indices.T = roi.getTPosition() - 1
        }
        [class_name:roi.getClass().getName(), type_code:roi.getType(),
         subpixel:roi.subPixelResolution(), indices:indices, roi:region]
    }

    def equivalent
    equivalent = { a, b ->
        if (a instanceof Number && b instanceof Number)
            return Double.isFinite(a as double) && Double.isFinite(b as double) &&
                Math.abs((a as double) - (b as double)) <= 0.0001d
        if (a instanceof Map && b instanceof Map)
            return a.keySet() == b.keySet() && a.every { key, value -> equivalent(value, b[key]) }
        if (a instanceof List && b instanceof List)
            return a.size() == b.size() && (0..<a.size()).every { equivalent(a[it], b[it]) }
        return a == b
    }
    def encode = { ij.gui.Roi roi ->
        def stream = new ByteArrayOutputStream()
        new ij.io.RoiEncoder(stream).write(roi)
        byte[] bytes = stream.toByteArray()
        boolean repaired = false
        if (roi instanceof ij.gui.RotatedRectRoi && (bytes[6] & 255) == 0 &&
                (bytes[48] & 255) == 0 && (bytes[49] & 255) == 5) {
            bytes[6] = 7 // fixed ij-1.54p RoiDecoder restores subtype only in FREEROI branch
            repaired = true
        }
        if (bytes.length > 32768) throw new IllegalArgumentException('Native ROI exceeds 32 KiB')
        [bytes:bytes, repaired:repaired]
    }
    def decode = { byte[] input, String filename ->
        byte[] bytes = input.clone()
        boolean repaired = false
        if ((bytes[6] & 255) == 0 && (bytes[48] & 255) == 0 && (bytes[49] & 255) == 5) {
            bytes[6] = 7
            repaired = true
        }
        [roi:new ij.io.RoiDecoder(bytes, filename).getRoi(), bytes:bytes, repaired:repaired]
    }
    def digest = { byte[] bytes ->
        java.security.MessageDigest.getInstance('SHA-256').digest(bytes).encodeHex().toString()
    }
    def proof = { ij.gui.Roi roi, byte[] bytes, boolean repaired ->
        [class_name:roi.class.name, type_code:roi.getType(), subpixel:roi.subPixelResolution(),
         byte_sha256:digest(bytes), encoded_bytes:bytes.length,
         rotated_header_repaired:repaired,
         spline_fit:roi instanceof ij.gui.PolygonRoi && roi.isSplineFit(),
         shape_path_values:roi instanceof ij.gui.ShapeRoi ? roi.getShapeAsArray().length : 0]
    }
    def zipBytes = { List<Map> entries, Map source ->
        def stream = new ByteArrayOutputStream()
        def zip = new ZipOutputStream(stream)
        for (entry in entries) {
            zip.putNextEntry(new ZipEntry(entry.name as String))
            zip.write(entry.bytes as byte[])
            zip.closeEntry()
        }
        if (source != null) {
            zip.putNextEntry(new ZipEntry('biofigure-source.json'))
            zip.write(JsonOutput.toJson(source).getBytes('UTF-8'))
            zip.closeEntry()
        }
        zip.close()
        byte[] result = stream.toByteArray()
        if (result.length > 1048576) throw new IllegalArgumentException('Native ZIP exceeds 1 MiB')
        result
    }

    String operation = request.operation as String
    if (operation in ['export_zip', 'export_roi']) {
        def collection = request.collection
        if (collection.items.isEmpty() || collection.items.size() > 64)
            throw new IllegalArgumentException('ROI export item count invalid')
        def entries = []
        def proofs = []
        for (item in collection.items) {
            def roi = construct(item.roi as Map)
            roi.setName(item.name as String)
            roi.setPosition(((item.indices.C ?: 0) as int) + 1,
                            ((item.indices.Z ?: 0) as int) + 1,
                            ((item.indices.T ?: 0) as int) + 1)
            if (roi instanceof ij.gui.PointRoi) {
                def region = item.roi
                roi.setCounters((0..<region.points.size()).collect { i ->
                    ((region.point_positions[i] as int) << 8) | (region.point_counters[i] as int)
                } as int[])
            }
            def before = describe(roi)
            def encoded = encode(roi)
            def decoded = decode(encoded.bytes as byte[], item.id + '.roi')
            def after = describe(decoded.roi as ij.gui.Roi)
            if (!equivalent(before, after) || decoded.roi.getName() != item.name)
                throw new IllegalArgumentException('Native ROI file cannot preserve geometry or properties: ' + item.roi.kind)
            entries.add([name:item.id + '.roi', bytes:encoded.bytes])
            proofs.add(proof(decoded.roi as ij.gui.Roi, encoded.bytes as byte[],
                             (encoded.repaired || decoded.repaired) as boolean))
        }
        if (operation == 'export_roi') {
            if (entries.size() != 1) throw new IllegalArgumentException('Single ROI export needs one item')
            payload = [ok:true, operation:operation, source_sha256:request.source_sha256,
                       roi_base64:(entries[0].bytes as byte[]).encodeBase64().toString(), proofs:proofs]
        } else {
            byte[] archive = zipBytes(entries, collection.source as Map)
            def manager = new ij.plugin.frame.RoiManager(false)
            def file = new File(report.parentFile, 'exchange-check.zip')
            try {
                file.bytes = archive
                if (!manager.runCommand('Open', file.absolutePath) || manager.getCount() != entries.size())
                    throw new IllegalArgumentException('RoiManager could not reopen exported ZIP')
                for (int i = 0; i < entries.size(); i++) {
                    if (!equivalent(describe(manager.getRoi(i)), describe(
                            decode(entries[i].bytes as byte[], entries[i].name as String).roi as ij.gui.Roi)))
                        throw new IllegalArgumentException('RoiManager changed exported ROI')
                }
            } finally { file.delete() }
            payload = [ok:true, operation:operation, source_sha256:request.source_sha256,
                       archive_base64:archive.encodeBase64().toString(), proofs:proofs]
        }
    } else if (operation in ['import_zip', 'import_roi']) {
        def entries = request.entries
        if (entries.isEmpty() || entries.size() > 64)
            throw new IllegalArgumentException('ROI import item count invalid')
        def items = []
        def repairedEntries = []
        for (entry in entries) {
            byte[] input = (entry.base64 as String).decodeBase64()
            if (input.length > 32768) throw new IllegalArgumentException('Imported ROI exceeds 32 KiB')
            def decoded = decode(input, entry.filename as String)
            def snapshot = describe(decoded.roi as ij.gui.Roi)
            def encoded = encode(decoded.roi as ij.gui.Roi)
            def again = decode(encoded.bytes as byte[], entry.filename as String)
            if (!equivalent(snapshot, describe(again.roi as ij.gui.Roi)))
                throw new IllegalArgumentException('Imported native ROI cannot be re-encoded faithfully')
            String name = decoded.roi.getName()?.trim()
            if (!name || name.size() > 80 || name.any { !Character.isDefined(it as char) })
                name = 'Imported ROI ' + (items.size() + 1)
            items.add([name:name, indices:snapshot.indices, roi:snapshot.roi,
                       proof:proof(decoded.roi as ij.gui.Roi, encoded.bytes as byte[],
                                   (decoded.repaired || encoded.repaired) as boolean)])
            repairedEntries.add([name:entry.filename, bytes:decoded.bytes])
        }
        if (operation == 'import_zip') {
            byte[] archive = zipBytes(repairedEntries, null)
            def manager = new ij.plugin.frame.RoiManager(false)
            def file = new File(report.parentFile, 'exchange-import-check.zip')
            try {
                file.bytes = archive
                if (!manager.runCommand('Open', file.absolutePath) || manager.getCount() != entries.size())
                    throw new IllegalArgumentException('RoiManager could not reopen imported ZIP')
                for (int i = 0; i < entries.size(); i++) {
                    if (!equivalent(describe(manager.getRoi(i)),
                                    describe(decode(repairedEntries[i].bytes as byte[],
                                                    repairedEntries[i].name as String).roi as ij.gui.Roi)))
                        throw new IllegalArgumentException('RoiManager changed imported ROI')
                }
            } finally { file.delete() }
        }
        payload = [ok:true, operation:operation, source_sha256:request.source_sha256,
                   items:items]
    } else throw new IllegalArgumentException('Unknown ROI exchange operation')
} catch (Throwable error) {
    payload = [ok:false, error_type:error.class.name, message:error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
