"""Prepare pinned Spring Boot Reference sources without modifying or relabelling them.

This is an audited scope adapter, not an AsciiDoc-to-Markdown converter. It writes
expanded AsciiDoc for the actual renderer/host, and copies every source file it
uses byte-for-byte. Missing includes, unsupported selectors and unexpected tag
syntax are fatal. Run with --source /path/to/spring-boot --output /tmp/input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

TAG = 'v4.2.0'
COMMIT = '3a36e91f4d92d2e5986092baf8fa1e4848098f01'
DOCS = Path('documentation/spring-boot-docs')
MODULES = DOCS / 'src/docs/antora/modules'
JAVA = DOCS / 'src/main/java/org/springframework/boot/docs'
ATTRS_FILE = Path('buildSrc/src/main/resources/org/springframework/boot/build/antora/antora-asciidoc-attributes.properties')
ANCHOR = re.compile(r'^\[\[([^\]]+)\]\]\s*$')
HEADING = re.compile(r'^(={1,6}) (.+)$')
MACRO = re.compile(r'^include-code::([^\[]+)\[(.*)\]\s*$')
INCLUDE = re.compile(r'^include::([^\[]+)\[(.*)\]\s*$')
MARKER = re.compile(r'//\s*(tag|end)::([^\[]+)\[\]')

# id, module/page, section anchor (None = full page), include subsections.
# 49 substantive Reference units plus one Tutorial-backed quickstart. Indexes, generated tables and runtime log
# samples are outside scope. Host-written wiki page organization may differ.
UNITS = [
 ('quickstart', 'tutorial:first-application/index', 'getting-started.first-application.code', True),
 ('using/project-structure', 'using/structuring-your-code', None, True),
 ('using/configuration-classes', 'using/configuration-classes', None, True),
 ('using/auto-configuration', 'using/auto-configuration', None, True),
 ('using/dependency-injection', 'using/spring-beans-and-dependency-injection', None, True),
 ('using/application-annotation', 'using/using-the-springbootapplication-annotation', None, True),
 ('using/running-applications', 'using/running-your-application', None, True),
 ('using/production-packaging', 'using/packaging-for-production', None, True),
 ('configuration/property-precedence', 'features/external-config', 'features.external-config', False),
 ('configuration/config-files', 'features/external-config', 'features.external-config.files', False),
 ('configuration/imports-and-configtrees', 'features/external-config', 'features.external-config.files.configtree', True),
 ('configuration/placeholders', 'features/external-config', 'features.external-config.files.property-placeholders', True),
 ('configuration/yaml', 'features/external-config', 'features.external-config.yaml', True),
 ('configuration/java-bean-binding', 'features/external-config', 'features.external-config.typesafe-configuration-properties.java-bean-binding', True),
 ('configuration/constructor-binding', 'features/external-config', 'features.external-config.typesafe-configuration-properties.constructor-binding', True),
 ('configuration/enabling-properties', 'features/external-config', 'features.external-config.typesafe-configuration-properties.enabling-annotated-types', True),
 ('configuration/relaxed-binding', 'features/external-config', 'features.external-config.typesafe-configuration-properties.relaxed-binding', True),
 ('configuration/properties-validation', 'features/external-config', 'features.external-config.typesafe-configuration-properties.validation', True),
 ('configuration/profiles', 'features/profiles', None, True),
 ('configuration/json', 'features/json', None, True),
 ('configuration/logging-levels', 'features/logging', 'features.logging.log-levels', True),
 ('web/controllers-and-routing', 'web/servlet', 'web.servlet.spring-mvc', False),
 ('web/mvc-auto-configuration', 'web/servlet', 'web.servlet.spring-mvc.auto-configuration', True),
 ('web/conversion-service', 'web/servlet', 'web.servlet.spring-mvc.conversion-service', True),
 ('web/message-converters', 'web/servlet', 'web.servlet.spring-mvc.message-converters', True),
 ('web/static-content', 'web/servlet', 'web.servlet.spring-mvc.static-content', True),
 ('web/content-negotiation', 'web/servlet', 'web.servlet.spring-mvc.content-negotiation', True),
 ('web/error-handling', 'web/servlet', 'web.servlet.spring-mvc.error-handling', True),
 ('web/cors', 'web/servlet', 'web.servlet.spring-mvc.cors', True),
 ('web/api-versioning', 'web/servlet', 'web.servlet.spring-mvc.api-versioning', True),
 ('web/embedded-server-customization', 'web/servlet', 'web.servlet.embedded-container.customizing', True),
 ('web/graceful-shutdown', 'web/graceful-shutdown', None, True),
 ('security/web-security', 'web/spring-security', None, True),
 ('validation/method-validation', 'io/validation', None, True),
 ('data/datasources', 'data/sql', 'data.sql.datasource', True),
 ('data/jdbc-template', 'data/sql', 'data.sql.jdbc-template', True),
 ('data/jpa-and-repositories', 'data/sql', 'data.sql.jpa-and-spring-data', True),
 ('data/r2dbc', 'data/sql', 'data.sql.r2dbc', True),
 ('testing/test-foundations', 'testing/spring-boot-applications', 'testing.spring-boot-applications', False),
 ('testing/detecting-configuration', 'testing/spring-boot-applications', 'testing.spring-boot-applications.detecting-configuration', True),
 ('testing/mock-environment', 'testing/spring-boot-applications', 'testing.spring-boot-applications.with-mock-environment', True),
 ('testing/running-server', 'testing/spring-boot-applications', 'testing.spring-boot-applications.with-running-server', True),
 ('testing/json-tests', 'testing/spring-boot-applications', 'testing.spring-boot-applications.json-tests', True),
 ('testing/mvc-tests', 'testing/spring-boot-applications', 'testing.spring-boot-applications.spring-mvc-tests', True),
 ('testing/jpa-tests', 'testing/spring-boot-applications', 'testing.spring-boot-applications.autoconfigured-spring-data-jpa', True),
 ('testing/testcontainers', 'testing/testcontainers', None, True),
 ('deployment/efficient-packaging', 'packaging/efficient', None, True),
 ('deployment/dockerfiles', 'packaging/container-images/dockerfiles', None, True),
 ('deployment/buildpacks', 'packaging/container-images/cloud-native-buildpacks', None, True),
 ('operations/actuator-enabling', 'actuator/enabling', None, True),
]


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def selection(text: str, anchor: str | None, descendants: bool = True) -> tuple[str, int, int]:
    """Select an explicit anchor/section, retaining exact original line positions."""
    lines = text.splitlines(keepends=True)
    if anchor is None:
        return text, 1, len(lines)
    start = next((i for i, line in enumerate(lines) if line.strip() == f'[[{anchor}]]'), None)
    if start is None:
        raise ValueError(f'Missing section anchor: {anchor}')
    h = start + 1
    while h < len(lines) and not HEADING.match(lines[h].rstrip('\n')):
        h += 1
    if h == len(lines):
        raise ValueError(f'No heading for {anchor}')
    level = len(HEADING.match(lines[h].rstrip('\n'))[1])
    end = len(lines)
    for i in range(h + 1, len(lines)):
        m = HEADING.match(lines[i].rstrip('\n'))
        if m and (not descendants or len(m[1]) <= level):
            end = i
            # A section anchor belongs to its following heading.
            while end > h + 1 and (ANCHOR.match(lines[end - 1].strip()) or not lines[end - 1].strip()):
                end -= 1
            break
    return ''.join(lines[start:end]), start + 1, end


def parse_options(value: str) -> dict[str, str]:
    out = {}
    if not value.strip():
        return out
    for item in re.split(r',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', value):
        k, sep, v = item.strip().partition('=')
        if not sep:
            raise ValueError(f'Unsupported positional include option: {item}')
        out[k] = v.strip().strip('"')
    allowed = {'tag', 'tags', 'indent', 'lines', 'title', 'subs', 'sync-group-id'}
    if set(out) - allowed:
        raise ValueError(f'Unsupported include options: {out}')
    if 'tag' in out and 'tags' in out:
        raise ValueError('Use either tag or tags, not both')
    return out


def select_code(text: str, options: dict[str, str]) -> tuple[str, list[int]]:
    """Implement Asciidoctor tag selectors used by the pinned selected source.

    '*' selects tagged regions; '**' selects all lines excluding tag markers;
    '!name' excludes that tag, named selectors include it. Marker comments are
    removed, but code before an inline end marker remains (e.g. '} // end::x[]').
    A missing/malformed selector is fatal rather than silently producing code.
    """
    selector = options.get('tag', options.get('tags'))
    selectors = selector.split(';') if selector else []
    active, found, selected, line_numbers = [], set(), [], []
    for num, original in enumerate(text.splitlines(), 1):
        line = original
        match = MARKER.search(line)
        emit = not selectors
        if selectors:
            positive = [s for s in selectors if not s.startswith('!')]
            negative = [s[1:] for s in selectors if s.startswith('!')]
            emit = (not positive or '**' in positive or ('*' in positive and bool(active))
                    or any(s in active for s in positive)) and not any(s in active for s in negative)
        if match:
            line = line[:match.start()].rstrip()
        if emit and (not match or line.strip()):
            selected.append(line)
            line_numbers.append(num)
        if match:
            name = match[2]
            found.add(name)
            if match[1] == 'tag':
                active.append(name)
            elif not active or active[-1] != name:
                raise ValueError(f'Unbalanced tag {name} at line {num}')
            else:
                active.pop()
    if active:
        raise ValueError(f'Unclosed tags: {active}')
    missing = {s.lstrip('!') for s in selectors} - {'*', '**'} - found
    if missing:
        raise ValueError(f'Missing code tags: {sorted(missing)}')
    if 'lines' in options:
        wanted = set()
        for part in options['lines'].split(';'):
            a, sep, b = part.partition('..')
            if sep:
                wanted.update(range(int(a), len(text.splitlines()) + 1 if b == '-1' else int(b) + 1))
            else:
                wanted.add(int(a))
        pairs = [(s, n) for s, n in zip(selected, line_numbers) if n in wanted]
        selected, line_numbers = [x[0] for x in pairs], [x[1] for x in pairs]
    # Asciidoctor include indent=0 removes the common leading whitespace.
    if 'indent' in options:
        indent = int(options['indent'])
        common = min((len(x) - len(x.lstrip()) for x in selected if x.strip()), default=0)
        selected = [(' ' * indent + x[common:]) if x.strip() else '' for x in selected]
    if not any(x.strip() for x in selected):
        raise ValueError(f'Empty code selection: {options}')
    return '\n'.join(selected) + '\n', line_numbers


class Preparer:
    def __init__(self, source: Path, output: Path):
        self.source, self.output = source.resolve(), output.resolve()
        self.sources: dict[str, dict] = {}
        self.expansions: list[dict] = []
        self.attributes = {'github-repo': 'spring-projects/spring-boot', 'github-ref': TAG,
                           'spring-boot-version': '4.2.0', 'revnumber': '4.2.0',
                           'asterisk': '*', 'nbsp': '\u00a0'}
        for line in self.read(ATTRS_FILE).splitlines():
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                self.attributes[k] = v
        # This is an input provenance note, not a claim that moving API versions
        # were fetched. Unsupported external URL attrs become pinned-source links.
        self.link_fallbacks: list[dict] = []

    def read(self, relative: Path) -> str:
        absolute = (self.source / relative).resolve()
        if not absolute.is_relative_to(self.source) or not absolute.is_file():
            raise ValueError(f'Missing or out-of-scope source: {relative}')
        raw = absolute.read_bytes()
        rel = absolute.relative_to(self.source).as_posix()
        self.sources[rel] = {'path': rel, 'sha256': sha(raw), 'bytes': len(raw)}
        copy = self.output / 'upstream' / rel
        copy.parent.mkdir(parents=True, exist_ok=True)
        if not copy.exists():
            shutil.copyfile(absolute, copy)
        elif copy.read_bytes() != raw:
            raise ValueError(f'Existing copied source changed: {copy}')
        return raw.decode('utf-8').replace('\r\n', '\n')

    def attrs(self, text: str) -> str:
        for _ in range(12):
            changed = re.sub(r'\{([\w-]+)\}', lambda m: self.attributes.get(m[1], m[0]), text)
            if changed == text:
                return text
            text = changed
        raise ValueError('Attribute substitution did not converge')

    def include_path(self, target: str, module: str, source: Path) -> Path:
        target = self.attrs(target)
        if ':' not in target and '$' not in target:
            return source.parent / target
        # Antora resource IDs used in this selected scope. Refuse external components.
        match = re.fullmatch(r'(?:(ROOT|reference):)?(example|partial)\$(.+)', target)
        if not match:
            raise ValueError(f'Unsupported include resource ID: {target}')
        mod, family, path = match.groups()
        mod = mod or module
        if mod == 'ROOT' and family == 'example':
            return DOCS / 'src/main' / path
        return MODULES / mod / ('examples' if family == 'example' else 'partials') / path

    def expand(self, text: str, source: Path, first_line: int = 1, module: str = 'reference', depth: int = 0) -> str:
        if depth > 10:
            raise ValueError('Include depth exceeded')
        out, current_id, pending_id = [], None, None
        # All chosen section chunks start with an explicit ID, as does full-page source.
        for lineno, line in enumerate(text.splitlines(), first_line):
            anchor = ANCHOR.match(line)
            if anchor:
                pending_id = anchor[1]
            elif HEADING.match(line):
                if pending_id:
                    current_id = pending_id
                pending_id = None
            elif line.strip():
                pending_id = None
            inc = MACRO.match(line)
            if inc:
                target, raw_options = inc.groups()
                if not current_id:
                    raise ValueError(f'include-code without section ID: {source}:{lineno}')
                package = current_id.replace('-', '').replace('.', '/')
                codepath = (JAVA / package / f'{target}.java')
                options = parse_options(raw_options)
                code, nums = select_code(self.read(codepath), options)
                record = {'kind': 'include-code', 'at': f'{source.as_posix()}#L{lineno}',
                          'source': (self.source / codepath).resolve().relative_to(self.source).as_posix(),
                          'selector': options, 'source_lines': nums, 'text': code, 'sha256': sha(code)}
                self.expansions.append(record)
                out.extend([f'// Source: {record["source"]}', '[source,java]', '----', code.rstrip('\n'), '----'])
                continue
            inc = INCLUDE.match(line)
            if inc:
                path = self.include_path(inc[1], module, source)
                options = parse_options(inc[2])
                contents = self.read(path)
                if options:
                    contents, nums = select_code(contents, options)
                else:
                    nums = list(range(1, len(contents.splitlines()) + 1))
                self.expansions.append({'kind': 'include', 'at': f'{source.as_posix()}#L{lineno}',
                                        'source': path.as_posix(), 'source_lines': nums,
                                        'selector': options, 'text': contents, 'sha256': sha(contents)})
                out.append(self.expand(contents, path, nums[0] if nums else 1, module, depth + 1))
                continue
            out.append(line)
        expanded = '\n'.join(out) + '\n'
        # Expand declared documentation attrs without altering configuration ${...}
        # and Java/JSON braces. Dynamic external library link attrs are preserved
        # as pinned original source links instead of guessing versioned URLs.
        # A Javadoc location attribute is not the class identifier. Retain
        # the target even when its external versioned URL cannot be resolved.
        def javadoc_location(m):
            attribute, target, options = m.groups()
            self.link_fallbacks.append({'attribute': attribute, 'source': source.as_posix(),
                                        'identifier_retained': target, 'replacement': 'inline-code'})
            return f'javadoc:{target}[{options}]'
        expanded = re.sub(r'javadoc:\{([^}]+)\}/([^\s\[]+)\[([^\]]*)\]', javadoc_location, expanded)
        expanded = self.attrs(expanded)
        def missing_external(m):
            resource, suffix, label = m.groups()
            url = f'https://github.com/spring-projects/spring-boot/blob/{COMMIT}/{source.as_posix()}#L{first_line}'
            self.link_fallbacks.append({'attribute': resource, 'suffix': suffix, 'source': source.as_posix(),
                                        'replacement': url})
            return f'{url}[{label or "Upstream reference"}]'
        expanded = re.sub(r'\{((?:url|version)-[\w-]+)\}([^\s\[]*)\[([^\]]*)\]', missing_external, expanded)
        # Turn xrefs into explicit pinned official reference links. A selected input
        # unit is not an Antora catalog, so do not invent local resolution.
        def xref(m):
            target, label = m.groups()
            if ':' in target:
                mod, target = target.split(':', 1)
            else:
                mod = module
            if mod not in {'reference', 'how-to', 'appendix', 'ROOT', 'tutorial', 'specification', 'maven-plugin', 'gradle-plugin'}:
                raise ValueError(f'Unsupported xref module: {mod}')
            if '#' in target:
                page, frag = target.split('#', 1)
            else:
                page, frag = target, ''
            if page:
                url = f'https://docs.spring.io/spring-boot/{TAG[1:]}/{"" if mod == "ROOT" else mod + "/"}{page.removesuffix(".adoc")}.html'
            else:
                # Preserve an intra-document anchor for the renderer.
                return f'<<{frag},{label}>>'
            return f'{url}{"#" + frag if frag else ""}[{label or page}]'
        expanded = re.sub(r'xref:([^\[\s]+)\[([^\]]*)\]', xref, expanded)
        if re.search(r'^include(?:-code)?::', expanded, re.M):
            raise ValueError(f'Unresolved include directive: {source}')
        return expanded

    def prepare(self) -> dict:
        units = []
        for unit_id, page, anchor, descendants in UNITS:
            module, sep, module_page = page.partition(':')
            module, page = (module, module_page) if sep else ('reference', page)
            source = MODULES / module / 'pages' / f'{page}.adoc'
            raw = self.read(source)
            chunk, first, last = selection(raw, anchor, descendants)
            n_before = len(self.expansions)
            expanded = self.expand(chunk, source, first, module)
            # Level 1 title avoids a renderer treating section-only chunks as body.
            expanded = re.sub(r'^(=+) ', '= ', expanded, count=1, flags=re.M)
            dest = self.output / 'prepared' / f'{unit_id}.adoc'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(expanded, encoding='utf-8')
            paragraphs = []
            for p in re.split(r'\n\s*\n', chunk):
                p = p.strip()
                if (len(p) > 80 and not p.startswith(('[', '=', '*', '-', '.', '|', 'include', ':', '//'))
                        and re.match(r'[A-Z][a-z]', p)):
                    paragraphs.append(p)
            units.append({'id': unit_id, 'slug': unit_id, 'source': source.as_posix(), 'start_line': first, 'end_line': last, 'source_start_line': first,
                          'source_end_line': last, 'anchor': anchor, 'includes_subsections': descendants,
                          'prepared': f'prepared/{unit_id}.adoc', 'prepared_sha256': sha(expanded),
                          'title': re.search(r'^= (.+)', expanded, re.M)[1],
                          'source_paragraphs': paragraphs[:6],
                          'expansions': self.expansions[n_before:]})
        for source in ['LICENSE.txt', 'gradle.properties', 'antora/package.json']:
            self.read(Path(source))
        result = {'tag': TAG, 'commit': COMMIT, 'units': units,
                  'sources': list(sorted(self.sources.values(), key=lambda x: x['path'])),
                  'external_link_fallbacks': self.link_fallbacks,
                  'scope_notes': [
                      '49 curated Reference input units plus Tutorial quickstart; Java examples only (Kotlin deliberately excluded).',
                      'Raw files copied byte-for-byte under upstream/; prepared/ is expanded AsciiDoc, not relabelled Markdown.',
                      'Generated starter/property tables and runtime log output are excluded; no missing includes are ignored.',
                      'Dynamic external dependency URL attributes without a locally generated Antora catalog link to their pinned original source instead of guessed destinations.',
                  ]}
        (self.output / 'units.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    actual = subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != COMMIT:
        raise SystemExit(f'Expected {COMMIT}, got {actual}')
    dirty = subprocess.check_output(['git', '-C', str(args.source), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if dirty:
        raise SystemExit('Refusing a modified upstream checkout; restore the pinned source first')
    if args.output.resolve().is_relative_to(args.source.resolve()):
        raise SystemExit('Output must be separate from upstream checkout')
    args.output.mkdir(parents=True, exist_ok=True)
    result = Preparer(args.source, args.output).prepare()
    print(json.dumps({'units': len(result['units']), 'sources': len(result['sources']),
                      'external_link_fallbacks': len(result['external_link_fallbacks'])}))


if __name__ == '__main__':
    main()
