const { createCanvas, loadImage } = require("canvas");
const config = require("./config");

function roundRect(ctx, x, y, w, h, r) {
  if (w < 2 * r) r = w / 2;
  if (h < 2 * r) r = h / 2;
  if (r < 0) r = 0;
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function formatVoice(minutes) {
  if (!minutes || minutes <= 0) return "0m";
  var h = Math.floor(minutes / 60);
  var m = minutes % 60;
  if (h > 0 && m > 0) return h + "h " + m + "m";
  if (h > 0) return h + "h";
  return m + "m";
}

function formatNumber(n) {
  if (!n) return "0";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

module.exports = async function renderTopCard(guildName, users, sortBy) {
  const W = 1280;

  const startY = 150;
  const rowHeight = 75;
  const rowGap = 18;

  var neededH = startY + users.length * (rowHeight + rowGap) + 20;
  var H = Math.max(720, neededH);

  var canvas = createCanvas(W, H);
  var ctx = canvas.getContext("2d");

  // ===== CYBER BACKGROUND =====
  var bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#070B16");
  bg.addColorStop(1, "#0E1628");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // subtle grid lines
  ctx.strokeStyle = "rgba(0,255,255,0.05)";
  ctx.lineWidth = 1;
  for (var g = 0; g < W; g += 80) {
    ctx.beginPath();
    ctx.moveTo(g, 0);
    ctx.lineTo(g, H);
    ctx.stroke();
  }

  // ===== TITLE =====
  ctx.fillStyle = "#00F5FF";
  ctx.font = "bold 48px sans-serif";
  ctx.fillText("\u25E4 SERVER LEADERBOARD \u25E2", 60, 80);

  ctx.fillStyle = "rgba(255,255,255,0.6)";
  ctx.font = "22px sans-serif";
  ctx.fillText(guildName, 60, 115);

  // determine if we show an extra stat column
  var showMessages = sortBy === "messages";
  var showVoice = sortBy === "voiceMinutes";
  var showStat = showMessages || showVoice;

  for (var i = 0; i < users.length; i++) {
    var u = users[i];
    var y = startY + i * (rowHeight + rowGap);
    var isTop = i === 0;

    // ===== GLASS PANEL =====
    roundRect(ctx, 50, y, W - 100, rowHeight, 18);
    ctx.fillStyle = "rgba(255,255,255,0.05)";
    ctx.fill();

    // ===== NEON BORDER =====
    if (i === 0) ctx.strokeStyle = "#00F5FF";
    else if (i === 1) ctx.strokeStyle = "#A0A0A0";
    else if (i === 2) ctx.strokeStyle = "#CD7F32";
    else ctx.strokeStyle = "rgba(255,255,255,0.1)";

    ctx.shadowColor = ctx.strokeStyle;
    ctx.shadowBlur = isTop ? 20 : 0;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // ===== AVATAR =====
    if (u.avatar) {
      try {
        var avatar = await loadImage(u.avatar);
        ctx.save();
        ctx.beginPath();
        ctx.arc(100, y + rowHeight / 2, isTop ? 30 : 24, 0, Math.PI * 2);
        ctx.clip();
        ctx.drawImage(
          avatar,
          100 - (isTop ? 30 : 24),
          y + rowHeight / 2 - (isTop ? 30 : 24),
          isTop ? 60 : 48,
          isTop ? 60 : 48
        );
        ctx.restore();
      } catch (err) {
        console.error("[TOP] Avatar failed for " + u.username + ":", err.message);
        var medalColors = ["#FFD700", "#C0C0C0", "#CD7F32", "#5865F2", "#57F287"];
        ctx.fillStyle = medalColors[Math.min(i, medalColors.length - 1)];
        ctx.beginPath();
        ctx.arc(100, y + rowHeight / 2, isTop ? 30 : 24, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#FFFFFF";
        ctx.font = isTop ? "bold 20px sans-serif" : "bold 16px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(u.username.charAt(0).toUpperCase(), 100, y + rowHeight / 2);
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
      }
    }

    // ===== POSITION =====
    ctx.fillStyle = "#FFFFFF";
    ctx.font = "bold 26px sans-serif";
    ctx.fillText("#" + (i + 1), 160, y + 47);

    // ===== USERNAME =====
    ctx.font = isTop ? "bold 28px sans-serif" : "bold 24px sans-serif";
    ctx.fillText(u.username, 230, y + 47);

    // ===== EXTRA STAT (messages / voice) =====
    if (showStat) {
      var statText = "";
      var statIcon = "";

      if (showMessages) {
        statIcon = "\u2709 ";
        statText = formatNumber(u.messages || 0) + " msgs";
      } else if (showVoice) {
        statIcon = "\uD83D\uDD0A ";
        statText = formatVoice(u.voiceMinutes || 0);
      }

      // glass pill background
      var pillX = 560;
      var pillW = 160;
      var pillH = 32;
      var pillY = y + rowHeight / 2 - pillH / 2;

      ctx.fillStyle = "rgba(255,255,255,0.07)";
      roundRect(ctx, pillX, pillY, pillW, pillH, 16);
      ctx.fill();

      ctx.strokeStyle = "rgba(255,255,255,0.12)";
      ctx.lineWidth = 1;
      roundRect(ctx, pillX, pillY, pillW, pillH, 16);
      ctx.stroke();

      // stat text
      ctx.fillStyle = "#00F5FF";
      ctx.font = "bold 18px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(statIcon + statText, pillX + pillW / 2, pillY + 22);
      ctx.textAlign = "left";
    }

    // ===== LEVEL =====
    ctx.font = "20px sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.8)";
    ctx.fillText("LVL " + u.level, W - 220, y + 47);

    // ===== PROGRESS BAR =====
    var needed = u.level * config.xp.multiplier;
    var pct = needed > 0 ? u.xp / needed : 0;

    var barW = 220;
    var barH = 8;
    var barX = W - 470;
    var barY2 = y + 42;

    roundRect(ctx, barX, barY2, barW, barH, 4);
    ctx.fillStyle = "rgba(255,255,255,0.15)";
    ctx.fill();

    var fillW = barW * pct;

    if (fillW > 0) {
      var actualFill = Math.max(fillW, barH);
      roundRect(ctx, barX, barY2, actualFill, barH, 4);

      var grad = ctx.createLinearGradient(barX, 0, barX + actualFill, 0);
      grad.addColorStop(0, "#00F5FF");
      grad.addColorStop(1, "#3B82F6");

      ctx.shadowColor = "#00F5FF";
      ctx.shadowBlur = 15;
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // crown for #1
    if (i === 0) {
      ctx.fillStyle = "#FFD700";
      ctx.font = "bold 34px sans-serif";
      ctx.fillText("\u2605", W - 130, y + 50);
    }
  }

  return canvas.toBuffer("image/png");
};