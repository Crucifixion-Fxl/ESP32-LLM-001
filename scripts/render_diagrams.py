#!/usr/bin/env python3
"""Generate reviewable, dependency-free SVG documentation diagrams."""
import argparse
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INK, MUTED, TEAL, BORDER = '#142d3b', '#576b78', '#087f8c', '#d6e2e7'


def start(title, subtitle, height):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{height}" viewBox="0 0 1080 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#087f8c"/></marker></defs>',
            f'<rect width="1080" height="{height}" rx="18" fill="#f8fbfc"/>',
            '<g font-family="Arial, Helvetica, sans-serif">',
            text(40, 46, title, 25, INK, '700'), text(40, 74, subtitle, 14)]


def text(x, y, value, size=13, color=MUTED, weight='400', anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'


def box(x, y, w, h, title, lines, accent=False):
    result = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{"#e9f5f5" if accent else "#ffffff"}" stroke="{TEAL if accent else BORDER}" stroke-width="1.5"/>',
              text(x+18, y+29, title, 16, INK, '700')]
    result += [text(x+18, y+56+i*21, line, 13) for i, line in enumerate(lines)]
    return ''.join(result)


def arrow(path, label=None, x=0, y=0, dashed=False):
    return (f'<path d="{path}" fill="none" stroke="{TEAL}" stroke-width="2" marker-end="url(#arrow)"'
            + (' stroke-dasharray="5 4"' if dashed else '') + '/>'
            + (text(x, y, label, 12, TEAL) if label else ''))


def finish(parts):
    return '\n'.join(parts + ['</g></svg>']) + '\n'


def architecture():
    p=start('Seven boards. One inference pipeline.', 'ESP32-LLM-001  /  Runtime topology  /  GPIO connections shown separately', 570)
    p += [box(40, 125, 210, 155, 'MASTER', ['BPE + INT4 embeddings', 'Final RMS norm + LM head', 'Sampling + USB console'], True)]
    for n,x,y in [(1,300,125),(2,550,125),(3,800,125),(4,800,345),(5,550,345),(6,300,345)]:
        p += [box(x,y,210,120,f'NODE {n}', [f'Transformer layers {(n-1)*4}–{n*4-1}', 'Ternary weights + KV cache'])]
    p += [arrow('M250 185 H300'),arrow('M510 185 H550'),arrow('M760 185 H800'),
          arrow('M905 245 V345','SPI',920,300),arrow('M800 405 H760'),arrow('M550 405 H510'),
          arrow('M300 405 H145 V280','Return hidden state',40,438),
          text(310,294,'Float32 hidden states  •  10 MHz SPI, mode 0  •  4 KB frames',14,TEAL),
          text(40,511,'Per board: 16 MB flash + 8 MB PSRAM. Six nodes execute 24 layers in sequence.',14,INK),
          text(40,537,'Model weights stay local. The master begins the next token after the result returns.',13)]
    return finish(p)


def workflow():
    p=start('From base weights to flashable artifacts.', 'ESP32-LLM-001  /  Recommended model workflow  /  Run Python modules from the repository root', 590)
    rows=[(40,120,'01  PREPARE',['Download Qwen2-0.5B','Crop vocabulary + embeddings','tools.prepare']),
          (395,120,'02  TRAIN',['Ternary QAT + INT8 activations','Checkpoint and export weights','tools.training.train_qat']),
          (750,120,'03  EXPORT',['Quantize INT4 embeddings','Pack tokenizer + board binaries','tools.export']),
          (750,345,'04  HOST CHECK',['Decode packed model on CPU','Check output and artifact layout','tools.validation.validate_int4']),
          (395,345,'05  FLASH',['Build master + node firmware','Flash firmware, then model data','scripts/flash_data.py']),
          (40,345,'06  BOARD CHECK',['Wire the seven-board chain','Inspect lane logs + serial output','Physical hardware required'])]
    for x,y,title,lines in rows:p.append(box(x,y,290,140,title,lines,title.startswith('06')))
    p += [arrow('M330 190 H395'),arrow('M685 190 H750'),arrow('M895 260 V345'),
          arrow('M750 415 H685'),arrow('M395 415 H330'),
          text(40,535,'Host decoding is a smoke check, not bit-exact emulation of the full firmware.',14,INK),
          text(40,560,'Artifacts: tokenizer.bin  •  embed.bin  •  final_norm.bin  •  six layers_START_to_END.bin files',13)]
    return finish(p)


def wiring():
    p=start('Wire each hop, then close the return path.', 'ESP32-S3 N16R8  /  GPIO numbers, not physical header positions  /  Power off while wiring', 630)
    p += [box(55,120,285,190,'UPSTREAM BOARD',['SPI transmitter','GPIO 4   ·  CS','GPIO 5   ·  MOSI','GPIO 7   ·  SCLK'],True),
          box(740,120,285,190,'DOWNSTREAM BOARD',['SPI receiver','GPIO 15  ·  CS','GPIO 16  ·  MOSI','GPIO 18  ·  SCLK'],True)]
    for y,label in [(197,'CS'),(218,'MOSI'),(239,'SCLK')]:
        p.append(arrow(f'M340 {y} H740',label,515,y-6))
    p += [text(55,342,'Repeat for Master → N1 → N2 → N3 → N4 → N5 → N6 → Master.',16,INK,'700'),
          box(55,368,970,62,'RESET CASCADE',[]),
          text(280,405,'GPIO 1 → next EN: Master through N5. Leave N6 GPIO 1 unconnected.',14),
          box(55,444,970,62,'READY RETURN',[]),
          text(280,481,'Node 6 GPIO 3 → Master GPIO 3.',14),
          text(55,548,'COMMON GROUND',14,INK,'700'),
          text(280,548,'Connect every board GND and the external supply negative terminal.',14),
          text(55,592,'Disconnect reset links for flashing. Do not feed external 5 V and USB power into the same board.',13)]
    return finish(p)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for name,source in [('architecture',architecture),('model-workflow',workflow),('wiring',wiring)]:
        destination=ROOT/'docs/images'/f'{name}.svg'
        content=source()
        if args.check:
            if not destination.exists() or destination.read_text()!=content:
                raise SystemExit(f'Outdated diagram: {destination.relative_to(ROOT)}')
        else:
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(content)
        print(f'{"Checked" if args.check else "Rendered"} {destination.relative_to(ROOT)}')


if __name__=='__main__':
    main()
