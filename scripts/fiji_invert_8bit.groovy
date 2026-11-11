#@ org.scijava.io.IOService ioService
#@ net.imagej.display.ImageDisplayService imageDisplayService
#@ org.scijava.command.CommandService commandService
#@ org.scijava.options.OptionsService optionsService

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

// Only backend generated paths and this fixed command are accepted by the caller.
def request = new JsonSlurper().parse(new File(System.getenv('BFS_FIJI_JOB_JSON') ?: ''))
def report = new File(request.output_path as String)
def output = new File(request.image_output_path as String)
def payload
int exitCode = 0
try {
    def dataset = ioService.open(new File(request.input_path as String).absolutePath)
    if (!(dataset instanceof net.imagej.Dataset) || dataset.numDimensions() != 2 ||
            dataset.getType().getBitsPerPixel() != 8 ||
            dataset.dimension(0) * dataset.dimension(1) > 16000000L ||
            dataset.axis(0).type().getLabel() != 'X' || dataset.axis(1).type().getLabel() != 'Y') {
        throw new IllegalArgumentException('Only single-plane XY 8-bit grayscale Dataset is supported')
    }
    def display = imageDisplayService.createImageDisplay(dataset)
    // Make the intended 8-bit p -> 255-p semantics explicit; Fiji's modern
    // mode instead inverts around the observed image min/max.
    optionsService.getOptions(net.imagej.options.OptionsCompatibility).setInvertModeLegacy()
    def module = commandService.run(net.imagej.plugins.commands.assign.InvertDataValues,
            true, 'display', display, 'allPlanes', true).get()
    if (module == null || module.isCanceled()) {
        throw new IllegalStateException('Fiji Invert command did not complete')
    }
    output.parentFile.mkdirs()
    ioService.save(dataset, output.absolutePath)
    payload = [ok: true, command: 'net.imagej.plugins.commands.assign.InvertDataValues',
               width: dataset.dimension(0), height: dataset.dimension(1)]
} catch (Throwable error) {
    output.delete()
    payload = [ok: false, error_type: error.class.name, message: error.message?.take(240)]
    exitCode = 2
}
report.parentFile.mkdirs()
report.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
System.exit(exitCode)
