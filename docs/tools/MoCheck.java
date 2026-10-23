import com.bedrockk.molang.MoLang;
import java.nio.file.*;
import java.util.*;

/** Parses every line of the input file with Cobblemon's MoLang parser; prints the ones that fail. */
public class MoCheck {
    public static void main(String[] args) throws Exception {
        List<String> lines = Files.readAllLines(Path.of(args[0]));
        int bad = 0;
        for (int i = 0; i < lines.size(); i++) {
            String s = lines.get(i);
            if (s.isBlank()) continue;
            try {
                MoLang.parse(s);
            } catch (Throwable t) {
                bad++;
                System.out.println("LINE " + (i + 1) + ": " + t + "\n   " + s);
            }
        }
        System.out.println("checked " + lines.size() + " expressions, " + bad + " failed");
    }
}
