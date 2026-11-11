#@ org.scijava.io.IOService ioService
// This one-off process only reads a backend-generated local asset and writes
// metadata. The caller controls the request path via a private environment
// variable; no user-provided script or command text is evaluated.

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def requestFile = new File(System.getenv('BFS_FIJI_JOB_JSON') ?: '')
def request = new JsonSlurper().parse(requestFile)
def output = new File(request.output_path as String)
def payload
int exitCode = 0
try {
    def input = new File(request.input_path as String)
    def opened = ioService.open(input.absolutePath)
    if (!(opened instanceof net.imagej.Dataset)) {
        throw new IllegalArgumentException('Fiji IOService returned ' + (opened == null ? 'null' : opened.class.name))
    }
    def axes = (0..<opened.numDimensions()).collect { index ->
        def axis = opened.axis(index)
        [name: axis?.type()?.getLabel(), length: opened.dimension(index),
         unit: axis?.unit(), scale: axis == null ? null : axis.calibratedValue(1.0d) - axis.calibratedValue(0.0d)]
    }
    def type = opened.getType()
    def bits = null
    try { bits = type.getBitsPerPixel() } catch (Throwable ignored) { }
    payload = [ok: true, axes: axes, pixel_type: type.class.name, bit_depth: bits,
               channels: axes.find { it.name?.equalsIgnoreCase('Channel') }?.length,
               source_name: opened.getName()]
} catch (Throwable error) {
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
output.parentFile.mkdirs()
output.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
