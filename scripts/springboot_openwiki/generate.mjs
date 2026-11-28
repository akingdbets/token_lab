import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [inputRoot, toolsRoot] = process.argv.slice(2);
if (!inputRoot || !toolsRoot) throw new Error('Usage: node generate.mjs INPUT_ROOT NODE_MODULES_ROOT');
const root = path.resolve(inputRoot);
const require = createRequire(path.join(path.resolve(toolsRoot), '__host__.cjs'));
const asciidoctor = require('@asciidoctor/core')();
const TurndownService = require('turndown');
const td = new TurndownService({ codeBlockStyle: 'fenced', headingStyle: 'atx', bulletListMarker: '-' });
td.use(require('turndown-plugin-gfm').gfm);
// The custom Spring macros need an Antora generated metadata catalog for link
// targets/property validation. Preserve the exact source identifiers and YAML
// instead; never synthesize defaults or non-existent Javadoc destinations.
function createRegistry() {
const registry = asciidoctor.Extensions.create();
registry.inlineMacro('javadoc', function () {
  this.process(function(parent, target, attrs) {
    const ref = target.split('/').pop();
    const [clazz, member] = ref.split('#');
    const name = attrs.format === 'full' ? clazz : clazz.split('.').pop().replaceAll('$', '.');
    const suffix = member ? '.' + member.replace(/([a-z]\w*\.)+/g, '') : '';
    const label = attrs.$positional?.[0];
    const text = label || ((attrs.format === 'annotation' ? '@' : '') + name + suffix);
    return this.createInline(parent, 'quoted', text, {type: 'monospaced'});
  });
});
registry.inlineMacro('configprop', function () {
  this.process(function(parent, target, attrs) {
    const value = attrs.format === 'envvar' ? target.replaceAll('.', '_').replaceAll('-', '').toUpperCase() : target;
    return this.createInline(parent, 'quoted', value, {type: 'monospaced'});
  });
});
registry.block('configprops', function () {
  this.onContext('listing'); this.positionalAttributes(['language']);
  this.process(function(parent, reader, attrs) {
    return this.createListingBlock(parent, reader.getLines(), {...attrs, style:'source', language:attrs.language || 'yaml'});
  });
});
return registry;
}
td.addRule('admonition', {filter(node) {return node.nodeName === 'TABLE' && /admonitionblock/.test(node.parentNode?.className || '');}, replacement(content,node) {const body=node.querySelector('td.content'); const label=node.querySelector('td.icon')?.textContent || 'Note'; return '\n\n> **'+label.trim()+':** '+td.turndown(body?.innerHTML || content).replaceAll('\n','\n> ')+'\n\n';}});
td.addRule('source-code', { filter: 'pre', replacement(content, node) {
  const code = node.querySelector('code');
  const lang = (code?.getAttribute('data-lang') || (code?.getAttribute('class') || '').match(/language-(\S+)/)?.[1] || '');
  const text = (code || node).textContent.replace(/\n$/, '');
  const fence = text.includes('```') ? '````' : '```';
  return '\n\n'+fence+lang+'\n'+text+'\n'+fence+'\n\n';
}});
td.addRule('reference-table', {
  filter(node) { return node.nodeName==='TABLE' && !/admonitionblock/.test(node.parentNode?.className || ''); },
  replacement(content,node) {
    const rows=Array.from(node.querySelectorAll('tr')).map(row=>Array.from(row.querySelectorAll('th,td')).map(cell=>td.turndown(cell.innerHTML).trim().replace(/\n+/g,'<br>').replace(/\|/g,'\\|')));
    if (!rows.length) return '';
    const width=Math.max(...rows.map(row=>row.length));
    if (!node.querySelector('th')) rows.unshift(Array(width).fill(''));
    const line=row=>'| '+row.join(' | ')+' |';
    return '\n\n'+[line(rows[0]),line(Array(width).fill('---')),...rows.slice(1).map(line)].join('\n')+'\n\n';
  }
});
const { HostSessionManager } = await import(pathToFileURL(path.join(path.resolve(toolsRoot), 'openwiki/dist/integrations/core/session-manager.js')));
const m = HostSessionManager.create({host: 'codex', producerActor: 'codex'});
const unitData = JSON.parse(await fs.readFile(path.join(root, 'units.json'),'utf8'));
const unitList = unitData.units.map(u => ({...u, title:u.title.replace(/[\x60\"]/g, '')}));
const begin = await m.begin({ root: path.resolve(inputRoot), mode: 'init', language: 'en' });
console.log('begin', JSON.stringify(begin));
const runId = begin.runId;
if (!runId) throw new Error('No runId');
const pagePath = u => `/openwiki/${u.slug}.md`;
const pages = unitList.map((u, i) => ({
  path: pagePath(u), title: u.title,
  purpose: u.purpose || `Explain ${u.title} using the pinned Spring Boot Reference and exact Java examples.`,
  seedPaths: ['upstream/' + u.source],
  relatedPages: [unitList[(i + 1) % unitList.length], unitList[(i + unitList.length - 1) % unitList.length]]
    .map(pagePath),
  instructions: ['English only. Preserve source semantics and exact identifiers/defaults. Do not introduce unsupported advice.']
}));
if (begin.phase === 'planning') console.log('plan', JSON.stringify(await m.submitPlan({ runId, pages })));
const log = [];
for (;;) {
  const result = await m.nextPage({ runId });
  if (result.status === 'complete') break;
  const job = result.job;
  const u = unitList.find(u => pagePath(u) === job.path);
  if (!u) throw new Error(`Unknown job ${job.path}`);
  const expanded = await fs.readFile(path.join(root, u.prepared), 'utf8');
  const rawSource = await fs.readFile(path.join(root, 'upstream', u.source), 'utf8');
  const rawSection = rawSource.split('\n').slice(u.start_line-1,u.end_line).join('\n');
  const level = rawSection.match(/^(=+) /m)?.[1].length || 1;
  let seenTitle = false;
  const renderInput = expanded.replace(/^(=+) /gm, (full, signs) => {
    if (!seenTitle) {seenTitle = true; return '= ';}
    return '='.repeat(Math.max(2, signs.length - level + 1)) + ' ';
  });
  const html = asciidoctor.convert(renderInput, {
    safe: 'secure', standalone: false, attributes: { 'showtitle': true, 'source-highlighter': 'none' }, extension_registry: createRegistry()
  });
  let md = td.turndown(html).replace(/\n{3,}/g, '\n\n').trim();
  // AsciiDoc IDs are not GitHub Markdown heading slugs. Turndown removes
  // empty anchor elements, so rewrite local links to their retained headings.
  const slug = title => title.toLowerCase().replace(/<[^>]*>/g,'').replace(/[^\w\- ]/g,'').replace(/ /g,'-');
  const anchors = new Map([...expanded.matchAll(/^\[\[([^\]]+)\]\]\s*\n=+ (.+)$/gm)].map(x => [x[1],slug(x[2])]));
  md = md.replace(/\]\(#([^)]*)\)/g, (whole,id) => {
    if (!anchors.has(id)) throw new Error(`Unresolved internal anchor ${u.slug}#${id}`);
    return '](#'+anchors.get(id)+')';
  });
  if (/include(?:-code)?::|javadoc:|configprops::/.test(md)) { await fs.writeFile('/private/tmp/tokenlab-springboot-render-failure.md', md); throw new Error(`Unresolved directive in ${u.slug}`); };
  // These pages are an English, source-preserving Reference edition, not free-form API advice.
  const desc = u.description || `Spring Boot ${u.title}: documented behavior, configuration and source-backed examples from v4.2.0.`;
  const fm = `---\ntype: guide\ntitle: ${JSON.stringify(u.title)}\ndescription: ${JSON.stringify(desc)}\ntags: ${JSON.stringify(['spring-boot', ...u.slug.split('/').slice(0, 1)])}\n---\n\n`;
  const neighbor = pages.find(p => p.path === job.path).relatedPages.map(p => {
    const target = p.replace('/openwiki/', '');
    const rel = path.posix.relative(path.posix.dirname(u.slug), target);
    const title = unitList.find(x => pagePath(x) === p).title;
    return `- [${title}](${rel})`;
  }).join('\n');
  const routing = u.slug === 'quickstart' ? '\n\n## Find a task\n\n' + [
    ['Controller and request/response handling','web/controllers-and-routing'],
    ['Validation','validation/method-validation'],['Security','security/web-security'],
    ['External configuration','configuration/property-precedence'],['Dependency injection','using/dependency-injection'],
    ['Testing','testing/test-foundations'],['Database access','data/datasources'],
    ['Error handling','web/error-handling'],['Deployment','deployment/dockerfiles'],
    ['Operations','operations/actuator-enabling']].map(([label,slug]) => `- [${label}](${slug}.md)`).join('\n') : '';
  const content = (fm + md + routing + '\n\n## Related topics\n\n' + neighbor + '\n').replace(/[ \t]+$/gm, '');
  const output = path.join(root, job.path.replace(/^\//, ''));
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.writeFile(output, content);
  // Retain substantive original prose as propositions; source ranges, not generated
  // Markdown, are the evidence. OpenWiki computes resource versions and claim IDs.
  const statements = [...html.matchAll(/<div class="paragraph">\s*<p>([\s\S]*?)<\/p>\s*<\/div>/g)]
    .map(x => td.turndown(x[1]).replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/`/g, '').replace(/\s+/g, ' ').trim())
    .filter(x => x.length > 85 && !x.endsWith(':') && !/^(For (example|instance)|The following|This example|See |To learn|For more)/.test(x));
  const resources = u.evidence || [`repo://upstream/${u.source}#L${u.start_line || 1}-L${u.end_line}`];
  const claims = [...new Set(statements)].slice(0, 6).map(statement => ({ statement,
    evidence: resources.map(resource => ({resource})) }));
  if (claims.length) claims[0].evidence.push(...[...new Set((u.expansions || []).map(e=>'repo://upstream/'+e.source))].map(resource=>({resource})));
  if (!claims.length) throw new Error(`No substantive original prose for ${u.slug}`);
  const completed = await m.submitPage({ runId, jobId: job.id, claims });
  console.log('page', job.path, JSON.stringify(completed));
  log.push({ page: job.path, jobId: job.id, result: completed });
}
const finish = await m.finish({ runId });
console.log('finish', JSON.stringify(finish));
if (finish.status !== 'complete') throw new Error('OpenWiki did not finish');
await fs.writeFile(path.join(root, 'generation-log.json'), JSON.stringify({begin,pages:log,finish},null,2)+'\n');
