"""Validate an independently generated Spring Boot wiki without touching FastAPI.

Requires the original staged OpenWiki input for evidence hash/range verification.
The corpus is loaded with OPENWIKI_DIR; write_manifest always receives a new path.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def dist(values):
    s = sorted(values)
    def q(p):
        pos = (len(s)-1)*p
        lo=int(pos); hi=min(lo+1,len(s)-1)
        return round(s[lo]+(s[hi]-s[lo])*(pos-lo), 2)
    return dict(min=min(s),p25=q(.25),median=statistics.median(s),p75=q(.75),p90=q(.9),p95=q(.95),max=max(s),mean=round(statistics.mean(s),2))

def fences(text):
    opened=None; blocks=[]; lines=[]
    # Ignore front matter, which can itself contain source URI fragments.
    if text.startswith('---\n'): text=text.split('\n---\n',1)[1]
    for line in text.splitlines():
        line=re.sub(r'^(?:> ?)+', '', line)
        m=re.match(r'^\s*(`{3,}|~{3,})(.*)$',line)
        if m:
            marker,rest=m.groups()
            if opened is None: opened=(marker,rest.strip()); lines=[]
            elif marker[0]==opened[0][0] and len(marker)>=len(opened[0]) and not rest.strip():
                blocks.append((opened[1],'\n'.join(lines))); opened=None
            else: lines.append(line)
        elif opened: lines.append(line)
    if opened: raise ValueError('Unclosed code fence')
    return blocks

def normalized(text):
    # Rendering must retain all non-whitespace code tokens. Source tag marker
    # comments and AsciiDoc callout comments are presentation instructions only.
    text=re.sub(r'//\s*(?:tag|end)::[^\[]+\[\].*$', '', text, flags=re.M)
    text=re.sub(r'\s*//\s*<\d+>\s*$', '', text,flags=re.M)
    return '\n'.join(line.strip() for line in text.splitlines() if line.strip())

def wiki_stats(folder, enc):
    rows=[]
    for p in sorted(folder.rglob('*.md')):
        rel=p.relative_to(folder).as_posix()
        if any(x.startswith('.') for x in p.relative_to(folder).parts) or p.name in ('SOURCE.md','INSTRUCTIONS.md'): continue
        rows.append({'path':rel,'tokens':len(enc.encode(p.read_text())), 'sha256':sha(p.read_bytes()), 'kind':'index' if p.name=='index.md' else ('quickstart' if rel=='quickstart.md' else 'topic')})
    nonindex=[r['tokens'] for r in rows if r['kind']!='index']
    return {'documents':len(rows),'topics':sum(r['kind']=='topic' for r in rows),'quickstarts':sum(r['kind']=='quickstart' for r in rows),'indexes':sum(r['kind']=='index' for r in rows),'non_index_pages':len(nonindex),'total_tokens':sum(r['tokens'] for r in rows),'non_index_tokens':sum(nonindex),'non_index_distribution':dist(nonindex),'all_document_distribution':dist([r['tokens'] for r in rows]),'per_document':rows}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--upstream',type=Path); ap.add_argument('--wiki',type=Path,default=ROOT/'data/openwiki/springboot-en'); ap.add_argument('--out',type=Path,default=ROOT/'docs/corpora/springboot/validation.json'); a=ap.parse_args()
    import tiktoken
    enc=tiktoken.get_encoding('o200k_base')
    errors=[]; warnings=[]; wik=a.wiki.resolve(); inp=a.input.resolve()
    original_manifest=ROOT/'data/corpus_manifest.jsonl'
    before=sha(original_manifest.read_bytes()) if original_manifest.exists() else None
    for p in wik.rglob('*.json'):
        try: json.loads(p.read_text())
        except Exception as e: errors.append(f'JSON {p.name}: {e}')
    manifest=json.loads((wik/'.page-manifest.json').read_text())
    stats=wiki_stats(wik,enc); stats_fast=wiki_stats(ROOT/'data/openwiki/en',enc)
    claims_count=evidence_count=0; source_paths=set(); snippets=Counter(); blocks_by_page={}
    for rel,record in manifest['pages'].items():
        rel=rel.removeprefix('/openwiki/'); p=wik/rel
        if record['pageVersion']!='sha256:'+sha(p.read_bytes()): errors.append('Manifest hash '+rel)
        cp=wik/'.claims'/Path(rel).with_suffix('.json')
        if not cp.exists(): errors.append('Missing claims '+rel); continue
        cj=json.loads(cp.read_text())
        if cj.get('pageVersion')!='sha256:'+sha(p.read_bytes()): errors.append('Claims page hash '+rel)
        for claim in cj['claims']:
            claims_count+=1
            for e in claim['evidence']:
                evidence_count+=1
                resource=e['resource']; path,_,frag=resource.removeprefix('repo://').partition('#'); src=inp/path; source_paths.add(path)
                if not resource.startswith('repo://') or not src.is_file(): errors.append('Evidence path '+resource); continue
                raw=src.read_bytes(); version=e['version']
                if frag:
                    m=re.fullmatch(r'L(\d+)(?:-L(\d+))?',frag)
                    if not m: errors.append('Unknown range '+resource); continue
                    lo,hi=int(m[1]),int(m[2] or m[1]); lines=raw.decode().splitlines(keepends=True)
                    if lo<1 or hi>len(lines) or lo>hi: errors.append('Evidence range '+resource); continue
                    expected='repo-lines-v1:sha256:'+sha(''.join(lines[lo-1:hi]).encode())
                    if not version.startswith(expected+':'): errors.append('Evidence range hash '+resource)
                elif version!='repo-file-v1:sha256:'+sha(raw): errors.append('Evidence file hash '+resource)
        try: blocks_by_page[rel]=fences(p.read_text())
        except ValueError as e: errors.append(f'{rel}: {e}')
        for lang,_ in blocks_by_page.get(rel,[]): snippets[lang or 'plain']+=1
        text=p.read_text()
        if re.search(r'include(?:-code)?::|javadoc:|configprops::',text): errors.append('Unresolved directive '+rel)
        if re.search(r'<(?:table|tbody|tr|td|pre|div)\b',text): errors.append('Raw renderer HTML '+rel)
        if 'Unresolved directive' in text or 'asciidoctor: ERROR' in text: errors.append('Renderer error '+rel)
    java_sources=[normalized(p.read_text()) for p in inp.rglob('*.java') if 'openwiki' not in p.parts]
    java_checked=0
    for rel,blocks in blocks_by_page.items():
        for lang,code in blocks:
            if lang=='java':
                java_checked+=1; norm=normalized(code)
                if not any(norm in src for src in java_sources): errors.append('Java code differs from preserved source '+rel)
    # Verify every source dependency, extraction, and rendered example independently.
    provenance=json.loads((inp/'units.json').read_text())
    raw_checked=expanded_checked=config_checked=inline_identifiers=internal_anchors=0
    for entry in provenance['sources']:
        raw=inp/'upstream'/entry['path']; raw_checked+=1
        if not raw.is_file() or sha(raw.read_bytes())!=entry['sha256']: errors.append('Raw source hash '+entry['path'])
    for u in provenance['units']:
        rel=u['slug']+'.md'; blocks=blocks_by_page.get(rel,[])
        prepared=(inp/u['prepared']).read_text()
        # Configuration listings must survive rendering with names, values and
        # string whitespace unchanged (only display indentation may differ).
        for language, code in re.findall(r'^\[(?:configprops|source),(yaml|properties)(?:,[^\]]*)?\]\n----\n(.*?)\n----', prepared, re.M|re.S):
            config_checked += 1
            if not any(lang==language and normalized(code)==normalized(out) for lang,out in blocks): errors.append('Configuration listing differs from source '+rel)
        rendered=(wik/rel).read_text()
        for target,options in re.findall(r'javadoc:([^\[\s]+)\[([^\]]*)\]',prepared):
            inline_identifiers+=1
            name=target.split('/')[-1].split('#')[0].split('.')[-1].replace('$','.')
            if name not in rendered: errors.append('Missing source Java identifier '+rel+': '+name)
        for anchor in re.findall(r'\]\(#([^)]*)\)',rendered):
            internal_anchors+=1
            headings=[re.sub(r'[^\w\- ]','',h.lower()).replace(' ','-') for h in re.findall(r'^#+ (.+)$',rendered,re.M)]
            if anchor not in headings: errors.append('Broken internal heading anchor '+rel+'#'+anchor)
        for annotation in re.findall(r'javadoc:([^\[\s]+)\[format=annotation\]',prepared):
            name='@'+annotation.split('#')[0].split('.')[-1].replace('$','.')
            if name not in rendered: errors.append('Missing source annotation '+rel+': '+name)
        for prop in re.findall(r'configprop:([^\[\s]+)\[\]',prepared):
            if prop not in rendered: errors.append('Missing source configuration name '+rel+': '+prop)
        if sha(prepared.encode())!=u['prepared_sha256']: errors.append('Prepared source hash '+rel)
        for expansion in u['expansions']:
            expanded_checked+=1
            if sha(expansion['text'].encode())!=expansion['sha256']: errors.append('Expansion hash '+rel)
            # Selections preserve source code tokens; tag markers alone are removed.
            source_lines=(inp/'upstream'/expansion['source']).read_text().splitlines()
            chosen='\n'.join(source_lines[n-1] for n in expansion['source_lines'])
            chosen=re.sub(r'//\s*(?:tag|end)::[^\[]+\[\].*', '', chosen)
            if normalized(chosen)!=normalized(expansion['text']): errors.append('Expansion differs from selected original lines '+rel)
            if expansion['kind']=='include-code' and not any(normalized(expansion['text'])==normalized(code) for lang,code in blocks if lang=='java'):
                errors.append('Missing rendered include-code '+rel+' '+expansion['source'])
    for rel in blocks_by_page:
        rendered=(wik/rel).read_text()
        headings={re.sub(r'[^\w\- ]','',title.lower()).replace(' ','-') for title in re.findall(r'^#{1,6} (.+)$',rendered,re.M)}
        for anchor in re.findall(r'\]\(#([^)]*)\)',rendered):
            if anchor not in headings: errors.append('Missing Markdown heading anchor '+rel+'#'+anchor)
    xrefs=[]
    if a.upstream:
        for row in provenance['sources']:
            original=a.upstream/row['path']
            if not original.is_file() or sha(original.read_bytes())!=row['sha256']: errors.append('Upstream original hash '+row['path'])
        for u in provenance['units']:
            text='\n'.join((a.upstream/u['source']).read_text().splitlines()[u['start_line']-1:u['end_line']])
            for target in re.findall(r'xref:([^\[\s]+)\[',text):
                mod='tutorial' if '/tutorial/' in u['source'] else 'reference'; t=target
                if ':' in t: mod,t=t.split(':',1)
                page,_,anchor=t.partition('#')
                if not page: source=Path(u['source'])
                elif mod in ('maven-plugin','gradle-plugin'): source=Path(f'build-plugin/spring-boot-{mod}/src/docs/antora/modules/{mod}/pages')/page
                else: source=Path('documentation/spring-boot-docs/src/docs/antora/modules')/mod/'pages'/page
                path=a.upstream/source; exists=path.is_file()
                anchor_ok=not anchor or exists and ('[['+anchor+']]') in path.read_text()
                generated=mod=='appendix' and anchor.startswith('appendix.application-properties.')
                if not exists or not anchor_ok and not generated: errors.append('Unresolved upstream xref '+target)
                xrefs.append({'unit':u['slug'],'target':target,'file_exists':exists,'anchor_verified':anchor_ok,'generated_anchor_not_built':generated and not anchor_ok})
    # corpus.py is used unchanged; importantly, the default corpus CLI is never called.
    os.environ['OPENWIKI_DIR']=str(wik); os.environ['TOKENIZER']='tiktoken:o200k_base'
    sys.path.insert(0,str(ROOT/'src'))
    from corpus import load_corpus,write_manifest
    corpus=load_corpus()
    broken={d.doc_id:d.broken_links for d in corpus if d.broken_links}
    if broken: errors.append('Broken internal Markdown links')
    separated=ROOT/'data/corpus_manifest.springboot-en.jsonl'
    write_manifest(corpus,separated)
    after=sha(original_manifest.read_bytes()) if original_manifest.exists() else None
    if before!=after: errors.append('FastAPI manifest changed')
    report={'tokenizer':'tiktoken:o200k_base','springboot':stats,'fastapi':stats_fast,'checks':{'json_parse':True,'manifest_pages':len(manifest['pages']),'claims':claims_count,'evidence_records':evidence_count,'evidence_source_files':len(source_paths),'raw_source_hashes':raw_checked,'expansions_source_matched':expanded_checked,'config_examples_source_matched':config_checked,'code_blocks':dict(snippets),'java_identifiers_checked':inline_identifiers,'local_heading_anchors_checked':internal_anchors,'java_blocks_source_matched':java_checked,'broken_links':broken,'corpus_documents':len(corpus),'corpus_links':sum(len(d.links) for d in corpus),'fastapi_manifest_unchanged':before==after,'separate_manifest':str(separated.relative_to(ROOT))},'upstream_xrefs':xrefs,'warnings':warnings,'errors':errors}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('springboot','fastapi')},ensure_ascii=False,indent=2)); print('Spring Boot:',{k:v for k,v in stats.items() if k!='per_document'}); print('FastAPI:',{k:v for k,v in stats_fast.items() if k!='per_document'})
    return bool(errors)
if __name__=='__main__': sys.exit(main())
