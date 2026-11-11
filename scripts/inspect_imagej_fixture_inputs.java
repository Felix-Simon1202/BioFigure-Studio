// Read-only test probe against the reviewed local ImageJ1 JAR. No Fiji plugins,
// commands, updater, network operations or user files are executed by this probe.
import ij.ImagePlus;
import ij.io.Opener;
import ij.measure.Calibration;
import ij.process.ImageProcessor;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

class ImageJFixtureProbe {
    static String sha256(Path path) throws IOException, java.security.NoSuchAlgorithmException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536];
            int length;
            while ((length = input.read(buffer)) != -1) digest.update(buffer, 0, length);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    static String quote(String text) {
        return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"";
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("fixture-directory output-json");
        File[] files = new File(args[0]).listFiles((dir, name) -> name.endsWith(".tif") || name.endsWith(".png"));
        if (files == null) throw new IOException("Fixture directory unavailable");
        Arrays.sort(files, Comparator.comparing(File::getName));
        Path imagejSource = Path.of(ImagePlus.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        String coreHash = sha256(imagejSource);
        try (BufferedWriter writer = Files.newBufferedWriter(Path.of(args[1]), StandardCharsets.UTF_8)) {
            writer.write("{\"imagej_version\":" + quote(ij.ImageJ.VERSION) + ",\"imagej_core_sha256\":" + quote(coreHash) + ",\"items\":[");
            boolean comma = false;
            for (File file : files) {
                if (comma) writer.write(",");
                comma = true;
                ImagePlus image = new Opener().openImage(file.getAbsolutePath());
                if (image == null) {
                    writer.write("{\"file\":" + quote(file.getName()) + ",\"opened\":false}");
                    continue;
                }
                try {
                    Calibration calibration = image.getCalibration();
                    writer.write("{\"file\":" + quote(file.getName()) + ",\"file_sha256\":" + quote(sha256(file.toPath()))
                        + ",\"opened\":true,\"width\":" + image.getWidth()
                        + ",\"height\":" + image.getHeight() + ",\"bit_depth\":" + image.getBitDepth()
                        + ",\"channels\":" + image.getNChannels() + ",\"z_slices\":" + image.getNSlices()
                        + ",\"frames\":" + image.getNFrames() + ",\"planes\":" + image.getStackSize()
                        + ",\"pixel_width\":" + calibration.pixelWidth + ",\"pixel_height\":" + calibration.pixelHeight
                        + ",\"pixel_depth\":" + calibration.pixelDepth + ",\"unit\":" + quote(calibration.getUnit())
                        + ",\"frame_interval\":" + calibration.frameInterval + ",\"time_unit\":" + quote(calibration.getTimeUnit())
                        + ",\"samples\":[");
                    for (int plane = 1; plane <= image.getStackSize(); plane++) {
                        if (plane > 1) writer.write(",");
                        ImageProcessor processor = image.getStack().getProcessor(plane);
                        writer.write("[");
                        for (int pixel = 0; pixel < processor.getPixelCount(); pixel++) {
                            if (pixel > 0) writer.write(",");
                            // RGB samples are packed integers; other samples use exact float values.
                            writer.write(image.getBitDepth() == 24 ? Integer.toString(processor.get(pixel)) : Double.toString(processor.getf(pixel)));
                        }
                        writer.write("]");
                    }
                    writer.write("]}");
                } finally {
                    image.close();
                    image.flush();
                }
            }
            writer.write("]}\n");
        }
        System.out.println("Inspected " + files.length + " generated fixtures with ImageJ " + ij.ImageJ.VERSION);
    }
}
