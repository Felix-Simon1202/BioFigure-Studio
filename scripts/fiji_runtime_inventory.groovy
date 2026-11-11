#@ org.scijava.command.CommandService commandService
#@ org.scijava.log.LogService logService
// Read-only metadata probe for the pinned, locally audited Fiji snapshot.
// Run headlessly with updater autocheck disabled; it does not execute commands.

import groovy.json.JsonOutput

def safeCall = { object, method ->
    try { object == null ? null : object."$method"() } catch (Throwable ignored) { null }
}

def commands = commandService.getCommands().collect { command ->
    def inputs = []
    try {
        inputs = command.inputs().collect { item ->
            [name: safeCall(item, 'getName'),
             label: safeCall(item, 'getLabel'),
             type: safeCall(item, 'getType')?.name,
             required: safeCall(item, 'isRequired'),
             default_value: safeCall(item, 'getDefaultValue')?.toString(),
             minimum_value: safeCall(item, 'getMinimumValue')?.toString(),
             maximum_value: safeCall(item, 'getMaximumValue')?.toString(),
             choices: safeCall(item, 'getChoices')?.collect { it?.toString() },
             visibility: safeCall(item, 'getVisibility')?.toString()]
        }
    } catch (Throwable ignored) { }
    [identifier: safeCall(command, 'getIdentifier'),
     title: safeCall(command, 'getTitle'),
     menu_path: safeCall(command, 'getMenuPath')?.toString(),
     class_name: safeCall(command, 'getDelegateClassName'),
     inputs: inputs]
}

def legacyCommands = []
try {
    legacyCommands = ij.Menus.getCommands().collect { name, implementation ->
        [label: name?.toString(), implementation: implementation?.toString()]
    }
} catch (Throwable error) {
    logService.warn('ImageJ1 menu enumeration unavailable: ' + error.class.name)
}

def payload = [schema_version: '1.0', scijava_commands: commands, imagej1_commands: legacyCommands]
def output = new File('work/fiji-runtime/runtime-commands.json')
output.parentFile.mkdirs()
output.text = JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n'
println('BFS_FIJI_INVENTORY scijava=' + commands.size() + ' imagej1=' + legacyCommands.size())
