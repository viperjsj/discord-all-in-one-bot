const { createCanvas, loadImage } = require('canvas');

function roundRect(ctx, x, y, width, height, radius) {
    if (width < 2 * radius) radius = width / 2;
    if (height < 2 * radius) radius = height / 2;
    if (radius < 0) radius = 0;
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
}

function formatVoice(minutes) {
    if (!minutes || minutes <= 0) return '0m';
    var h = Math.floor(minutes / 60);
    var m = minutes % 60;
    if (h > 0 && m > 0) return h + 'h ' + m + 'm';
    if (h > 0) return h + 'h';
    return m + 'm';
}

function getRankColor(rank) {
    if (rank === 1) return '#FFD700';  // gold
    if (rank === 2) return '#A0A0A0';  // silver
    if (rank === 3) return '#CD7F32';  // bronze
    return '#5865F2';                  // default blurple
}

module.exports = async (member, userData, rank, requiredXP) => {

    var width = 1000;
    var height = 400;

    var canvas = createCanvas(width, height);
    var ctx = canvas.getContext('2d');

    // === BACKGROUND ===
    var bg = ctx.createLinearGradient(0, 0, width, height);
    bg.addColorStop(0, '#0a0a2a');
    bg.addColorStop(0.3, '#1a1a4a');
    bg.addColorStop(0.7, '#1a1a4a');
    bg.addColorStop(1, '#0a0a2a');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, width, height);

    // Subtle grid for depth
    ctx.strokeStyle = 'rgba(100, 100, 255, 0.08)';
    ctx.lineWidth = 1;
    for (var gx = 0; gx < width; gx += 50) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, height); ctx.stroke();
    }
    for (var gy = 0; gy < height; gy += 50) {
        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(width, gy); ctx.stroke();
    }

    // === GLASS PANEL ===
    ctx.fillStyle = 'rgba(255,255,255,0.08)';
    roundRect(ctx, 40, 40, width - 80, height - 80, 30);
    ctx.fill();

    // === AVATAR ===
    var avatarSize = 160;
    var avatarX = 90;
    var avatarY = height / 2 - avatarSize / 2;
    var acx = avatarX + avatarSize / 2;
    var acy = avatarY + avatarSize / 2;

    // Neon ring
    ctx.shadowColor = '#00C6FF';
    ctx.shadowBlur = 25;
    ctx.beginPath();
    ctx.arc(acx, acy, avatarSize / 2 + 6, 0, Math.PI * 2);
    ctx.strokeStyle = '#00C6FF';
    ctx.lineWidth = 5;
    ctx.stroke();
    ctx.shadowBlur = 0;

    try {
        var avatar = await loadImage(
            member.user.displayAvatarURL({ extension: 'png', size: 512 })
        );
        ctx.save();
        ctx.beginPath();
        ctx.arc(acx, acy, avatarSize / 2, 0, Math.PI * 2);
        ctx.clip();
        ctx.drawImage(avatar, avatarX, avatarY, avatarSize, avatarSize);
        ctx.restore();
    } catch (err) {
        console.error("[RANK] Avatar failed:", err.message);
        var colors = ['#5865F2', '#00C6FF', '#57F287', '#FEE75C', '#EB459E'];
        ctx.fillStyle = colors[member.user.username.length % colors.length];
        ctx.beginPath();
        ctx.arc(acx, acy, avatarSize / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 60px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(member.user.username.charAt(0).toUpperCase(), acx, acy);
        ctx.textAlign = 'left';
        ctx.textBaseline = 'alphabetic';
    }

    // === USERNAME ===
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 42px sans-serif';
    ctx.fillText(member.user.username, 300, 115);

    // === LEVEL ===
    ctx.fillStyle = '#cccccc';
    ctx.font = '28px sans-serif';
    ctx.fillText('LEVEL ' + userData.level, 300, 155);

    // === RANK BADGE ===
    var rankColor = getRankColor(rank);

    ctx.fillStyle = rankColor;
    roundRect(ctx, width - 240, 75, 170, 50, 25);
    ctx.fill();

    // subtle glow for top 3
    if (rank <= 3) {
        ctx.shadowColor = rankColor;
        ctx.shadowBlur = 15;
        roundRect(ctx, width - 240, 75, 170, 50, 25);
        ctx.fill();
        ctx.shadowBlur = 0;
    }

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 24px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('RANK #' + rank, width - 155, 108);
    ctx.textAlign = 'left';

    // === STATS ROW ===
    var statsY = 190;
    var statItems = [
        { label: 'MESSAGES',   value: String(userData.messages || 0) },
        { label: 'VOICE TIME', value: formatVoice(userData.voiceMinutes || 0) },
        { label: 'TOTAL XP',   value: String(userData.totalXp || 0) },
    ];

    var statBoxW = 175;
    var statBoxH = 52;
    var statGap = 18;
    var statStartX = 300;

    for (var si = 0; si < statItems.length; si++) {
        var sx = statStartX + si * (statBoxW + statGap);
        var s = statItems[si];

        // box background
        ctx.fillStyle = 'rgba(255,255,255,0.06)';
        roundRect(ctx, sx, statsY, statBoxW, statBoxH, 12);
        ctx.fill();

        // box border
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1;
        roundRect(ctx, sx, statsY, statBoxW, statBoxH, 12);
        ctx.stroke();

        // label
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(s.label, sx + statBoxW / 2, statsY + 18);

        // value
        ctx.fillStyle = '#00C6FF';
        ctx.font = 'bold 18px sans-serif';
        ctx.fillText(s.value, sx + statBoxW / 2, statsY + 42);

        ctx.textAlign = 'left';
    }

    // === PROGRESS BAR ===
    var barWidth = 600;
    var barHeight = 30;
    var barX = 300;
    var barY = 272;

    var progress = requiredXP > 0 ? Math.min(userData.xp / requiredXP, 1) : 0;
    var filled = barWidth * progress;

    // background
    ctx.fillStyle = 'rgba(255,255,255,0.15)';
    roundRect(ctx, barX, barY, barWidth, barHeight, 15);
    ctx.fill();

    // gradient fill
    if (filled > 0) {
        var gradient = ctx.createLinearGradient(barX, 0, barX + barWidth, 0);
        gradient.addColorStop(0, '#5865F2');
        gradient.addColorStop(1, '#00C6FF');
        ctx.fillStyle = gradient;
        roundRect(ctx, barX, barY, Math.max(filled, barHeight), barHeight, 15);
        ctx.fill();
    }

    // % text
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 20px sans-serif';
    ctx.fillText(Math.floor(progress * 100) + '%', barX + barWidth - 65, barY - 8);

    // XP text
    ctx.fillStyle = '#ffffff';
    ctx.font = '18px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(userData.xp + ' / ' + requiredXP + ' XP', barX + barWidth, barY + 55);
    ctx.textAlign = 'left';

    return canvas.toBuffer('image/png');
};