import json
import re
import html
from bs4 import BeautifulSoup

def clean_title(title_raw):
    if not title_raw:
        return ""
    t = title_raw.strip()
    # remove leading digits and punctuation like "1 - - ", "329 - -. "
    t = re.sub(r'^\s*\d+\s*[-–—.]+\s*[-–—.]*\s*', '', t).strip()
    t = re.sub(r'^[–—\-.\s]+', '', t).strip()
    if t.startswith('¡ ') or t.startswith('¿ '):
        t = t[0] + t[2:].strip()
    # Also clean multiple internal spaces
    t = re.sub(r'\s+', ' ', t)
    return t

def extract_lines(text_elem):
    html_content = text_elem.decode_contents()
    text = re.sub(r'<br\s*/?>', '\n', html_content)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    
    raw_lines = [l.strip() for l in text.split('\n')]
    cleaned_lines = []
    for l in raw_lines:
        if l:
            cleaned_l = re.sub(r'[ \t]+', ' ', l).strip()
            if cleaned_l:
                cleaned_lines.append(cleaned_l)
    return cleaned_lines

def parse_stanzas_smart(article):
    body = article.find(class_='hymn-body')
    if not body:
        return []
    
    stanzas_elems = body.find_all(class_='stanza')
    parsed_stanzas = []
    
    for s_el in stanzas_elems:
        h4 = s_el.find('h4')
        section_type_raw = h4.get_text(strip=True) if h4 else ''
        
        text_el = s_el.find(class_='stanza-text')
        if not text_el:
            continue
            
        lines = extract_lines(text_el)
        
        current_type = "coro" if "CORO" in section_type_raw.upper() else "estrofa"
        current_label = section_type_raw
        current_lines = []
        
        for line in lines:
            m = re.match(r'^(\d+)\s*v?[\.\s]*$', line, re.IGNORECASE)
            if m:
                num_found = int(m.group(1))
                if current_lines:
                    v_num = None
                    m_num = re.search(r'\d+', current_label)
                    if m_num:
                        v_num = int(m_num.group())
                    parsed_stanzas.append({
                        'numero': v_num if current_type == "estrofa" else None,
                        'tipo': current_type,
                        'etiqueta': current_label,
                        'lineas': current_lines,
                        'texto': '\n'.join(current_lines)
                    })
                    current_lines = []
                current_label = f"Estrofa {num_found}"
                current_type = "estrofa"
            else:
                current_lines.append(line)
                
        if current_lines:
            v_num = None
            m_num = re.search(r'\d+', current_label)
            if m_num:
                v_num = int(m_num.group())
            parsed_stanzas.append({
                'numero': v_num if current_type == "estrofa" else None,
                'tipo': current_type,
                'etiqueta': current_label,
                'lineas': current_lines,
                'texto': '\n'.join(current_lines)
            })
            
    return parsed_stanzas

def build_full_lyrics(stanzas):
    blocks = []
    for s in stanzas:
        label = s['etiqueta'].upper()
        content = s['texto']
        blocks.append(f"[{label}]\n{content}")
    return "\n\n".join(blocks)

def extract_chorus(stanzas):
    for s in stanzas:
        if s['tipo'] == 'coro':
            return s['texto']
    return None

def main():
    with open('himnario_raw.html', 'r', encoding='utf-8') as f:
        html_doc = f.read()
        
    soup = BeautifulSoup(html_doc, 'html.parser')
    articles = soup.find_all('article', class_='hymn-item')
    print(f"Total articles in HTML: {len(articles)}")
    
    # 1. Build RAW export (exact 1:1)
    raw_list = []
    for idx, art in enumerate(articles):
        h2 = art.find(class_='hymn-title')
        raw_title = h2.get_text(strip=True) if h2 else ''
        body = art.find(class_='hymn-body')
        stanzas_raw = []
        if body:
            for s_div in body.find_all(class_='stanza'):
                h4 = s_div.find('h4')
                lbl = h4.get_text(strip=True) if h4 else ''
                txt_el = s_div.find(class_='stanza-text')
                lines = extract_lines(txt_el) if txt_el else []
                stanzas_raw.append({
                    'etiqueta': lbl,
                    'lineas': lines,
                    'texto': '\n'.join(lines)
                })
        raw_list.append({
            'indice': idx,
            'id': art.get('id', ''),
            'data_num': art.get('data-num', ''),
            'data_title': art.get('data-title', ''),
            'titulo': raw_title,
            'secciones': stanzas_raw
        })
        
    with open('himnario_gloria_y_triunfo_raw.json', 'w', encoding='utf-8') as f:
        json.dump(raw_list, f, ensure_ascii=False, indent=2)
    print("Saved himnario_gloria_y_triunfo_raw.json")
    
    # 2. Build Curated / Cleaned Export
    fragment_224_stanzas = None
    cleaned_articles = []
    
    for idx, art in enumerate(articles):
        num_str = art.get('data-num', '')
        title_attr = art.get('data-title', '').strip().lower()
        
        # Check if this is the "Himno 2" continuation fragment
        if num_str == '2' and 'himno 2' in title_attr:
            fragment_224_stanzas = parse_stanzas_smart(art)
            print(f"Captured continuation fragment for hymn 224 from article index {idx}")
            continue
            
        cleaned_articles.append((idx, art))
        
    curated_hymns = []
    
    for idx, art in cleaned_articles:
        num_str = art.get('data-num', '')
        num_val = int(num_str) if num_str.isdigit() else 0
        h2 = art.find(class_='hymn-title')
        title_raw = h2.get_text(strip=True) if h2 else ''
        title_clean = clean_title(title_raw)
        title_norm = re.sub(r'\s+', ' ', title_raw.upper())
        
        correction_note = None
        
        # Check duplicate 25 -> 26
        if num_val == 25 and 'ALLI NO HABRA TRIBULACION' in title_norm:
            num_val = 26
            correction_note = "En el HTML original aparecía con data-num=25; corresponde al Himno 26 ('Allí no habrá tribulación')."
            
        # Check duplicate 248 -> 250
        if num_val == 248 and 'AL CANSADO PEREGRINO' in title_norm:
            num_val = 250
            correction_note = "En el HTML original aparecía con data-num=248; corresponde al Himno 250 ('Al cansado peregrino')."
            
        stanzas = parse_stanzas_smart(art)
        
        # If this is hymn 224, attach the missing stanzas
        if num_val == 224 and fragment_224_stanzas:
            for f_st in fragment_224_stanzas:
                stanzas.append(f_st)
            correction_note = "Se integraron las estrofas 2 y 3 que estaban traspapeladas bajo 'Himno 2' en el archivo original."
            
        # Ensure verse numbering is clean
        v_counter = 1
        for st in stanzas:
            if st['tipo'] == 'estrofa':
                if not st['numero']:
                    st['numero'] = v_counter
                v_counter = max(v_counter, st['numero'] + 1)
                st['etiqueta'] = f"Estrofa {st['numero']}"
            elif st['tipo'] == 'coro':
                st['etiqueta'] = "CORO"
                st['numero'] = None
                
        hymn_obj = {
            'id': num_val,
            'numero': num_val,
            'titulo': title_clean,
            'titulo_original': title_raw,
            'coro': extract_chorus(stanzas),
            'estrofas': stanzas,
            'letra_completa': build_full_lyrics(stanzas),
            'metadata': {
                'data_num_original': num_str,
                'id_html': art.get('id', ''),
                'nota_correccion': correction_note
            }
        }
        curated_hymns.append(hymn_obj)
        
    curated_hymns.sort(key=lambda x: x['numero'])
    
    # Check if there are any duplicate numbers remaining
    from collections import Counter
    counts = Counter(h['numero'] for h in curated_hymns)
    remaining_dups = [k for k, v in counts.items() if v > 1]
    if remaining_dups:
        print(f"WARNING: Duplicates remaining: {remaining_dups}")
    else:
        print("SUCCESS: All hymn numbers are strictly unique!")
        
    output_data = {
        'himnario': "Himnos de Gloria y Triunfo",
        'fuente': "https://elhimnologo.com/wp-content/uploads/2026/04/himnario_gloria_y_triunfo.html",
        'total_himnos': len(curated_hymns),
        'himnos': curated_hymns
    }
    
    with open('himnario_gloria_y_triunfo.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"Saved himnario_gloria_y_triunfo.json with {len(curated_hymns)} hymns.")

if __name__ == '__main__':
    main()
