const { registerFont, createCanvas, loadImage } = require("canvas");
const path = require("path");
const fs = require("fs");

// ===== FONT REGISTRATION =====
const systemPaths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
];

for (const fp of systemPaths) {
    if (fs.existsSync(fp)) {
        try {
            const bold = fp.toLowerCase().includes("bold");
            registerFont(fp, { family: "Sans", weight: bold ? "bold" : "normal" });
            registerFont(fp, { family: "sans-serif", weight: bold ? "bold" : "normal" });
        } catch (e) {}
    }
}

// ===== RUNNER =====
const type = process.argv[2];
if (!type) { console.error("No type"); process.exit(1); }

let data = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", function(chunk) { data += chunk; });

process.stdin.on("end", async function() {
    try {
        if (!data) { console.error("No input"); process.exit(1); }

        const payload = JSON.parse(data);

        const mockUser = (username, avatarUrl) => ({
            username: username || "User",
            displayAvatarURL: () => avatarUrl || "https://cdn.discordapp.com/embed/avatars/0.png"
        });

        let buffer;

        if (type === "levelup") {
            const render = require("./levelup");
            buffer = await render(
                mockUser(payload.username, payload.avatarURL),
                payload.level,
                payload.xp,
                payload.rank,
                payload.totalXp
            );
        }
        else if (type === "rank") {
            const render = require("./rank");
            buffer = await render(
                { user: mockUser(payload.username, payload.avatarURL) },
                payload.userData, payload.rank, payload.requiredXP
            );
        }
        else if (type === "top") {
            const render = require("./top");
            buffer = await render(payload.guildName, payload.users, payload.sortBy || "level");
        }
        else { console.error("Unknown type: " + type); process.exit(1); }

        if (buffer && buffer.length > 100) {
            process.stdout.write(buffer);
        } else {
            console.error("Empty buffer");
            process.exit(1);
        }
    } catch (error) {
        console.error("Render error:", error.message);
        process.exit(1);
    }
});