"""Safety and source fidelity checks for the Spring Boot scope adapter."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'scripts/springboot_openwiki/prepare.py'
spec = importlib.util.spec_from_file_location('springboot_prepare', MODULE)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class SourceSelectionTest(unittest.TestCase):
    def test_section_boundaries_exclude_following_anchor(self):
        text = '[[a]]\n= A\n\nintro\n\n[[a.child]]\n== Child\nbody\n\n[[b]]\n= B\nlast\n'
        selected, first, last = prepare.selection(text, 'a', False)
        self.assertEqual((first, last), (1, 4))
        self.assertNotIn('[[a.child]]', selected)
        selected, _, _ = prepare.selection(text, 'a', True)
        self.assertIn('body', selected)
        self.assertNotIn('[[b]]', selected)

    def test_missing_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, 'Missing section'):
            prepare.selection('= Intro\ntext', 'missing')

    def test_catalog_has_50_distinct_topics(self):
        ids = [u[0] for u in prepare.UNITS]
        self.assertEqual(len(ids), 50)
        self.assertEqual(len(set(ids)), 50)


class TaggedCodeTest(unittest.TestCase):
    TEXT = 'package example;\nclass Demo {\n\t// tag::method[]\n\tvoid run() {\n\t} // end::method[]\n}\n'

    def test_named_tag_retains_code_before_inline_end(self):
        code, lines = prepare.select_code(self.TEXT, {'tag': 'method'})
        self.assertEqual(code, '\tvoid run() {\n\t}\n')
        self.assertEqual(lines, [4, 5])

    def test_excluded_tag_preserves_surrounding_java(self):
        code, lines = prepare.select_code(self.TEXT, {'tag': '!method'})
        self.assertEqual(code, 'package example;\nclass Demo {\n}\n')
        self.assertEqual(lines, [1, 2, 6])

    def test_wildcard_and_indent(self):
        code, _ = prepare.select_code(self.TEXT, {'tags': '*', 'indent': '0'})
        self.assertEqual(code, 'void run() {\n}\n')

    def test_all_tagged_and_untagged_lines(self):
        code, _ = prepare.select_code(self.TEXT, {'tags': '**'})
        self.assertIn('package example;', code)
        self.assertIn('\t}', code)
        self.assertNotIn('tag::', code)

    def test_missing_or_unbalanced_tag_fails(self):
        for text, opts in [(self.TEXT, {'tag': 'absent'}), ('// tag::a[]\nx\n', {}),
                           ('// end::a[]\nx\n', {})]:
            with self.assertRaises(ValueError):
                prepare.select_code(text, opts)

    def test_unsupported_selection_option_is_fatal(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            prepare.parse_options('imaginary=true')


class IncludeResolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'repo'
        self.output = Path(self.tmp.name) / 'input'
        attrs = self.source / prepare.ATTRS_FILE
        attrs.parent.mkdir(parents=True)
        attrs.write_text('url-official=https://example.invalid\n')
        self.preparer = prepare.Preparer(self.source, self.output)

    def test_java_include_uses_heading_id_not_inline_anchor(self):
        code = self.source / prepare.JAVA / 'features/config/MyBean.java'
        code.parent.mkdir(parents=True)
        code.write_text('class MyBean { }\n')
        text = '[[features.config]]\n= Config\n\n[[an-example-not-a-section]]\nSome text.\ninclude-code::MyBean[]\n'
        expanded = self.preparer.expand(text, Path('page.adoc'))
        self.assertIn('class MyBean { }', expanded)
        self.assertIn('[source,java]', expanded)
        self.assertNotIn('include-code::', expanded)
        self.assertEqual(self.preparer.expansions[0]['source_lines'], [1])

    def test_external_javadoc_url_does_not_erase_class_identifier(self):
        text = 'javadoc:{url-testcontainers-mongodb-javadoc}/org.testcontainers.mongodb.MongoDBContainer[]\n'
        out = self.preparer.expand(text, Path('page.adoc'))
        self.assertEqual(out.strip(), 'javadoc:org.testcontainers.mongodb.MongoDBContainer[]')
        self.assertEqual(self.preparer.link_fallbacks[0]['identifier_retained'], 'org.testcontainers.mongodb.MongoDBContainer')

    def test_missing_include_is_fatal(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            self.preparer.expand('include::ROOT:partial$generated-table.adoc[]\n', Path('page.adoc'))

    def test_path_traversal_is_fatal(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.write_text('not input')
        with self.assertRaisesRegex(ValueError, 'out-of-scope'):
            self.preparer.read(Path('../outside'))

    def test_bytes_preserved_and_configuration_placeholders_untouched(self):
        target = self.source / 'example.properties'
        raw = b'name=${APP_NAME:demo}\r\nserver.port=8080\r\n'
        target.write_bytes(raw)
        text = self.preparer.read(Path('example.properties'))
        self.assertEqual((self.output / 'upstream/example.properties').read_bytes(), raw)
        self.assertIn('${APP_NAME:demo}', self.preparer.attrs(text))
        self.assertEqual(self.preparer.sources['example.properties']['sha256'], prepare.sha(raw))


if __name__ == '__main__':
    unittest.main()
