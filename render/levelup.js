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

module.exports = async function renderLevelUpCard(user, level, xp, rank, totalXp) {
  var W = 1000;
  var H = 300;

  var canvas = createCanvas(W, H);
  var ctx = canvas.getContext("2d");

  var bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#0A0F1C");
  bg.addColorStop(1, "#111827");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  var radial = ctx.createRadialGradient(W / 2, 0, 100, W / 2, H / 2, 600);
  radial.addColorStop(0, "rgba(59,130,246,0.1)");
  radial.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = radial;
  ctx.fillRect(0, 0, W, H);

  roundRect(ctx, 40, 40, W - 80, H - 80, 20);
  ctx.fillStyle = "rgba(255,255,255,0.05)";
  ctx.fill();

  ctx.strokeStyle = "rgba(59,130,246,0.4)";
  ctx.lineWidth = 2;
  ctx.shadowColor = "rgba(59,130,246,0.4)";
  ctx.shadowBlur = 20;
  ctx.stroke();
  ctx.shadowBlur = 0;

  try {
    var avatar = await loadImage(
      user.displayAvatarURL({ extension: "png", size: 256 })
    );
    ctx.save();
    ctx.beginPath();
    ctx.arc(140, H / 2, 60, 0, Math.PI * 2);
    ctx.clip();
    ctx.drawImage(avatar, 80, H / 2 - 60, 120, 120);
    ctx.restore();
  } catch (err) {
    console.error("[LEVELUP] Avatar failed:", err.message);
    var colors = ["#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444"];
    ctx.fillStyle = colors[user.username.length % colors.length];
    ctx.beginPath();
    ctx.arc(140, H / 2, 60, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#FFFFFF";
    ctx.font = "bold 48px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(user.username.charAt(0).toUpperCase(), 140, H / 2);
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  ctx.fillStyle = "#FFFFFF";
  ctx.font = "bold 42px sans-serif";
  ctx.fillText("LEVEL UP", 260, 120);

  ctx.font = "28px sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.85)";
  ctx.fillText(user.username + " reached level " + level, 260, 165);

  var needed = level * config.xp.multiplier;
  var pct = needed > 0 ? Math.min(xp / needed, 1) : 0;

  var barW = 400;
  var barH = 12;
  var barX = 260;
  var barY = 200;

  roundRect(ctx, barX, barY, barW, barH, 6);
  ctx.fillStyle = "rgba(255,255,255,0.15)";
  ctx.fill();

  var rawFillW = barW * pct;
  if (rawFillW > 0) {
    var fillW = Math.max(rawFillW, barH);
    roundRect(ctx, barX, barY, fillW, barH, 6);
    var grad = ctx.createLinearGradient(barX, 0, barX + fillW, 0);
    grad.addColorStop(0, "#3B82F6");
    grad.addColorStop(1, "#60A5FA");
    ctx.fillStyle = grad;
    ctx.fill();
  }

  ctx.fillStyle = "rgba(255,255,255,0.6)";
  ctx.font = "18px sans-serif";
  ctx.fillText(xp + " / " + needed + " XP", barX, barY + 32);

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.font = "bold 18px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(Math.floor(pct * 100) + "%", barX + barW, barY + 32);
  ctx.textAlign = "left";

  var statsX = 740;
  var boxW = 200;
  var boxH = 45;
  var gap = 12;
  var firstBoxY = 70;

  roundRect(ctx, statsX, firstBoxY, boxW, boxH, 10);
  ctx.fillStyle = "rgba(255,255,255,0.06)";
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  roundRect(ctx, statsX, firstBoxY, boxW, boxH, 10);
  ctx.stroke();

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("RANK", statsX + boxW / 2, firstBoxY + 16);
  ctx.fillStyle = "#60A5FA";
  ctx.font = "bold 20px sans-serif";
  ctx.fillText("#" + (rank || "?"), statsX + boxW / 2, firstBoxY + 38);
  ctx.textAlign = "left";

  var box2Y = firstBoxY + boxH + gap;
  roundRect(ctx, statsX, box2Y, boxW, boxH, 10);
  ctx.fillStyle = "rgba(255,255,255,0.06)";
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  roundRect(ctx, statsX, box2Y, boxW, boxH, 10);
  ctx.stroke();

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("NEXT LEVEL XP", statsX + boxW / 2, box2Y + 16);
  ctx.fillStyle = "#60A5FA";
  ctx.font = "bold 20px sans-serif";
  ctx.fillText(String(needed), statsX + boxW / 2, box2Y + 38);
  ctx.textAlign = "left";

  var box3Y = box2Y + boxH + gap;
  roundRect(ctx, statsX, box3Y, boxW, boxH, 10);
  ctx.fillStyle = "rgba(255,255,255,0.06)";
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  roundRect(ctx, statsX, box3Y, boxW, boxH, 10);
  ctx.stroke();

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("TOTAL XP", statsX + boxW / 2, box3Y + 16);
  ctx.fillStyle = "#60A5FA";
  ctx.font = "bold 20px sans-serif";
  ctx.fillText(String(totalXp || 0), statsX + boxW / 2, box3Y + 38);
  ctx.textAlign = "left";

  return canvas.toBuffer("image/png");
};