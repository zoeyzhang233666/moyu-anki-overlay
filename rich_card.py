"""Quiet, stable rich-text capsules for the desktop review overlay."""
from __future__ import annotations

import html
import json
import re

_SCRIPT = re.compile(r'<script\b[^>]*>.*?</script\s*>', re.I | re.S)
_TYPE = re.compile(r'\[\[\s*type\s*:[^\]]*\]\]|\{\{\s*type\s*:[^}]*\}\}', re.I)
_SOUND = re.compile(r'\[sound:[^\]]*\]', re.I)
_STYLE = re.compile(r'<style\b[^>]*>.*?</style\s*>', re.I | re.S)
_ANSWER = re.compile(r'<hr\b[^>]*\bid\s*=\s*[\"\x27]?answer\b[^>]*>', re.I)


def _markup(raw: str) -> str:
    raw = _SCRIPT.sub('', raw)
    raw = re.sub(r'\s+on[a-z]+\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27|[^\s>]+)', '', raw, flags=re.I)
    return _SOUND.sub('', _TYPE.sub('', raw))


def document(front: str, back: str, note: str = '', *, font_family='PingFang SC', font_size=13, mathjax=False) -> str:
    family = html.escape(json.dumps(str(font_family), ensure_ascii=False), quote=False)
    size = max(11, min(24, int(font_size)))
    front, back, note = _markup(front), _markup(back), _markup(note)
    styles = ''.join(_STYLE.findall(front) + _STYLE.findall(back))
    front, back = _STYLE.sub('', front), _STYLE.sub('', back)
    split = _ANSWER.search(back)
    if split:
        back = back[split.end():]
    fallback = f'<aside class="moyu-extra-note note"><div class="note-text">{note}</div></aside>' if note else ''
    # MathJax assets are served by Anki's local server (same origin as the
    # card page, whose base URL is mw.serverURL()). This mirrors reviewer.js.
    mathjax_head = ''
    if mathjax:
        mathjax_head = '''
<script>window.__moyuMathjax = true;</script>
<script src="/_anki/js/mathjax.js"></script>
<script src="/_anki/js/vendor/mathjax/tex-chtml-full.js"></script>'''
    return '''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">''' + styles + mathjax_head + f'''
<style>
:root {{ --moyu-size:{size}px; --moyu-note:{size}px; }}
*,*::before,*::after {{ user-select:none !important; -webkit-user-select:none !important;
    -webkit-user-drag:none !important; cursor:default !important; animation:none !important; transition:none !important; scroll-behavior:auto !important; }}
html, body {{ margin:0 !important; padding:0 !important; min-height:0 !important;
    width:100% !important; height:auto !important; background:transparent !important; overflow:hidden !important; }}
body {{ font-family:{family} !important; color:#000000 !important; text-align:left !important; }}
#moyu-content {{ width:100%; max-height:100vh; box-sizing:border-box; padding:0;
    overflow-wrap:anywhere; display:flow-root; overflow-y:auto; overflow-x:hidden;
    scrollbar-gutter:stable; }}
#moyu-front {{ display:flow-root; width:fit-content; max-width:100%; box-sizing:border-box;
    border-radius:11px; padding:5px 12px; background:#ffffff;
    height:auto !important; max-height:none !important; overflow:visible !important; }}
#moyu-back {{ display:none; margin-top:5px; min-width:0; visibility:hidden; pointer-events:none; }}
body.moyu-expanded #moyu-back {{ display:flow-root; visibility:visible; pointer-events:auto; }}
#moyu-content .wrap, #moyu-content .card-box {{ width:100% !important; max-width:none !important;
    padding:0 !important; margin:0 !important; display:block !important;
    border:none !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; }}
#moyu-front, #moyu-front *:not(mjx-container):not(mjx-container *):not(mjx-assistive-mml):not(mjx-assistive-mml *) {{ font-size:var(--moyu-size) !important; line-height:1.5 !important;
    text-align:left !important; font-weight:400; }}
#moyu-content mjx-container {{ font-size:var(--moyu-size) !important; line-height:normal !important; }}
#moyu-content mjx-container mjx-math {{ line-height:normal !important; }}
#moyu-content mjx-assistive-mml {{ display:none !important; }}
#moyu-front, #moyu-front .question {{ color:#000000 !important; }}
#moyu-front .question, #moyu-front p {{ margin:0 !important; }}
#moyu-front .note, #moyu-front #note, #moyu-front .notes {{ display:none !important; }}
#moyu-back .question, #moyu-back .question-back, #moyu-back #front {{ display:none !important; }}
#moyu-back .answer, #moyu-back .moyu-answer, #moyu-back #back {{
    width:fit-content !important; max-width:100% !important; box-sizing:border-box;
    padding:5px 12px !important; margin:0 !important; background:#ffffff !important;
    color:#000000 !important; border:0 !important; border-radius:11px !important;
    font-size:var(--moyu-size) !important; line-height:1.5 !important;
    text-align:left !important; height:auto !important; max-height:none !important; overflow:visible !important; }}
#moyu-back .answer *, #moyu-back .moyu-answer *, #moyu-back #back * {{ font-size:inherit !important; }}
#moyu-back .answer p, #moyu-back .moyu-answer p {{ margin:0; }}
#moyu-content .note, #moyu-content #note, #moyu-content .notes {{
    width:100% !important; max-width:100% !important; box-sizing:border-box;
    margin:5px 0 0 !important; padding:8px 12px !important; border:0 !important;
    border-radius:11px !important; background:#ffffff !important;
    height:auto !important; max-height:none !important; overflow:visible !important; }}
#moyu-content .note-text, #moyu-content .note-text * {{ font-size:var(--moyu-note) !important;
    line-height:1.6 !important; }}
#moyu-content .note-text {{ color:#000000 !important; }}
#moyu-content .note-section-title {{ font-size:{max(11,size-2)}px !important; color:#000000 !important;
    line-height:1.5 !important; margin:0 0 3px !important; font-weight:600 !important; color:#000000 !important; }}
#moyu-content .note-section + .note-section {{ margin-top:7px !important; padding-top:7px !important;
    border-top:1px solid rgba(100,110,130,.1) !important; }}
#moyu-content .note strong, #moyu-content .note b {{ font-weight:600 !important; }}
#moyu-content .note-text p {{ margin:0 0 5px; }}
#moyu-content .type-result, #moyu-content .input-area, #moyu-content #typeans,
#moyu-content .divider, #moyu-content input, #moyu-content button {{ display:none !important; }}
#moyu-content img, #moyu-content video {{ max-width:100% !important; height:auto; }}
#moyu-content pre {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
#moyu-content table {{ max-width:100%; table-layout:fixed; }}
::-webkit-scrollbar {{ width:3px; }}
::-webkit-scrollbar-thumb {{ background:rgba(110,110,115,.18); border-radius:3px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
</style></head><body class="card"><main id="moyu-content">
<section id="moyu-front">{front}</section>
<section id="moyu-back">{back}{fallback}</section>
</main><script>
(() => {{
    const front = document.getElementById('moyu-front');
    const back = document.getElementById('moyu-back');
    document.addEventListener('selectstart', event => event.preventDefault());
    document.addEventListener('dragstart', event => event.preventDefault());
    const labels = /^(question|answer|note|notes|front|back|问题|答案|正面|背面|笔记|备注|注释)\\s*[:：]?$/i;
    document.querySelectorAll('.label,.note-label,label').forEach(el => {{
        if (labels.test(el.textContent.trim())) el.style.setProperty('display','none','important');
    }});
    const extra = back.querySelector('.moyu-extra-note');
    const originalNote = back.querySelector('.note:not(.moyu-extra-note),#note,.notes');
    if (extra && (originalNote || (extra.textContent.trim() &&
        back.textContent.replace(extra.textContent,'').includes(extra.textContent.trim())))) extra.remove();
    document.querySelectorAll('.note,#note,.notes').forEach(el => {{
        const content = el.querySelector('.note-text') || el;
        if (!content.textContent.replace(/\\u00a0/g,' ').trim() && !content.querySelector('img,video'))
            el.style.setProperty('display','none','important');
    }});
    if (!back.querySelector('.answer,#back')) {{
        const answer = document.createElement('div'); answer.className='moyu-answer';
        [...back.childNodes].forEach(node => {{
            if (!(node.nodeType===1 && node.matches('.note,#note,.notes'))) answer.append(node);
        }});
        back.prepend(answer);
    }}
    // Ordinary template greys become pure black. Explicit inline colors and
    // chromatic highlights remain intact rather than being flattened to black.
    const nodes = [...document.querySelectorAll('#moyu-front,#moyu-front *,#moyu-back,#moyu-back *')];
    const specified = new WeakMap();
    nodes.forEach(el => {{
        const color = el.style.getPropertyValue('color') || el.getAttribute('color');
        if (color) {{ specified.set(el,color); el.style.setProperty('color',color,'important'); }}
    }});
    nodes.forEach(el => {{
        let parent = el;
        while (parent && !specified.has(parent)) parent = parent.parentElement;
        if (parent) return;
        const rgb = getComputedStyle(el).color.match(/^rgba?\\(([^)]+)\\)/);
        if (!rgb) return;
        const values = rgb[1].split(/[, /]+/).map(Number);
        if (Math.max(...values.slice(0,3))-Math.min(...values.slice(0,3)) <= 24 &&
            (values.length < 4 || values[3] >= .99))
            el.style.setProperty('color','#000000','important');
    }});
    window.moyuHeight = () => {{
        // Capsules use their natural height. Only the complete card scrolls
        // when it exceeds the fixed native surface's available screen space.
        // -1 tells the host that MathJax is still typesetting; it retries.
        if (window.__moyuMathjax && window.__moyuMathDone === undefined) return -1;
        return Math.ceil(document.getElementById('moyu-content').getBoundingClientRect().bottom);
    }};
    window.moyuSetExpanded = expanded => {{
        document.body.classList.toggle('moyu-expanded',expanded);
        return window.moyuHeight();
    }};
    if (window.__moyuMathjax) {{
        // Same contract as reviewer.js: wait for startup.promise, then
        // typeset the visible card once. mjx layout then settles.
        MathJax.startup.promise.then(function() {{
            return MathJax.typesetPromise([document.getElementById('moyu-content')]);
        }}).then(function() {{
            window.__moyuMathDone = 1;
        }}).catch(function() {{
            window.__moyuMathDone = -1;
        }});
    }}
}})();
</script></body></html>'''
