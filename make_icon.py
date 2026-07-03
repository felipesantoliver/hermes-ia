# ===================== GERADOR DO icon.ico =====================
# Gera icon.ico (multiresolução: 16, 32, 48, 256px) a partir de um desenho
# vetorial simples desenhado em código — sem depender de nenhuma imagem
# externa. Usa as cores do theme.css (roxo escuro) como identidade visual.
# Rode uma vez: `python make_icon.py`. build.py chama isso automaticamente
# se icon.ico não existir.

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit(
        "Pillow não instalado. Rode: pip install pillow --break-system-packages "
        "(ou apenas `pip install pillow` dentro do seu venv)."
    )

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "icon.ico"

BG = (18, 14, 28, 255)        # roxo quase-preto, combina com --bg-deep
ACCENT = (139, 92, 246, 255)  # roxo vívido, combina com --purple
ACCENT_SOFT = (196, 165, 255, 255)


def draw_master(size: int) -> Image.Image:
    """Desenha um símbolo simples: um círculo (o 'H' orbital do Hermes,
    referência abstrata a nó/rede, não a nenhuma marca de terceiros) sobre
    fundo arredondado."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = int(size * 0.06)
    radius = int(size * 0.22)
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=radius, fill=BG)

    cx, cy = size / 2, size / 2
    r_outer = size * 0.30
    r_inner = size * 0.11

    draw.ellipse(
        [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
        outline=ACCENT_SOFT,
        width=max(1, int(size * 0.035)),
    )
    draw.ellipse(
        [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
        fill=ACCENT,
    )

    # Três "satélites" — remete ao orquestrador multi-agente do Hermes
    import math
    for angle_deg in (90, 210, 330):
        angle = math.radians(angle_deg)
        sx = cx + r_outer * math.cos(angle)
        sy = cy + r_outer * math.sin(angle)
        sr = size * 0.045
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=ACCENT_SOFT)

    return img


def main() -> None:
    master = draw_master(256)
    sizes = [16, 32, 48, 256]
    master.save(
        OUT_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print(f"✅ icon.ico gerado em {OUT_PATH} ({', '.join(str(s) for s in sizes)}px)")


if __name__ == "__main__":
    main()