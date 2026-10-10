// Bundle Monaco locally (no CDN) with only the pieces OptLens needs.
import 'monaco-editor/esm/vs/editor/edcore.main';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import { loader } from '@monaco-editor/react';

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };

// Minimal x86-64 Intel-syntax highlighter for the assembly diff.
monaco.languages.register({ id: 'x86asm' });
monaco.languages.setMonarchTokensProvider('x86asm', {
  ignoreCase: true,
  tokenizer: {
    root: [
      [/^\s*[.\w$@]+:/, 'type.identifier'], // labels
      [/^\s*\.[a-z_]+/, 'keyword.directive'], // directives
      [/"([^"\\]|\\.)*"/, 'string'],
      [/[#;].*$/, 'comment'],
      [/^\s*[a-z][a-z0-9]*/, 'keyword'], // mnemonic
      [
        /\b(?:[re]?(?:ax|bx|cx|dx|si|di|sp|bp|ip)|r(?:8|9|1[0-5])[dwb]?|[abcd][lh]|[sd]il|[bs]pl|[xyz]mm\d+|k[0-7])\b/,
        'variable.predefined',
      ],
      [/\b(?:byte|word|dword|qword|xmmword|ymmword|zmmword|ptr|offset)\b/, 'keyword.size'],
      [/-?\b0x[0-9a-f]+\b|-?\b\d+\b/, 'number'],
      [/\.L[\w.$]+|[A-Za-z_][\w.$@]*/, 'identifier'],
    ],
  },
});

const shared = (dark: boolean): monaco.editor.ITokenThemeRule[] => [
  { token: 'keyword', foreground: dark ? 'a99cff' : '5b47e0' },
  { token: 'keyword.directive', foreground: dark ? '7d8590' : '6e7781' },
  { token: 'keyword.size', foreground: dark ? '7d8590' : '6e7781' },
  { token: 'type.identifier', foreground: dark ? 'f0b45b' : 'a15c00', fontStyle: 'bold' },
  { token: 'variable.predefined', foreground: dark ? '6cc5d9' : '0b7285' },
  { token: 'number', foreground: dark ? 'e8a08a' : 'b4441b' },
  { token: 'string', foreground: dark ? '9ece6a' : '2f7d32' },
  { token: 'comment', foreground: dark ? '5c6370' : '8b949e', fontStyle: 'italic' },
];

monaco.editor.defineTheme('optlens-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: shared(true),
  colors: {
    'editor.background': '#0e0f13',
    focusBorder: '#00000000',
    'editor.lineHighlightBackground': '#ffffff08',
    'editorLineNumber.foreground': '#3b3f4a',
    'editorLineNumber.activeForeground': '#9aa0ac',
    'editorGutter.background': '#0e0f13',
    'editor.selectionBackground': '#8b7bff40',
    'editorIndentGuide.background1': '#1d2027',
    'scrollbarSlider.background': '#ffffff14',
    'scrollbarSlider.hoverBackground': '#ffffff22',
    'diffEditor.insertedLineBackground': '#2ea04318',
    'diffEditor.insertedTextBackground': '#2ea04330',
    'diffEditor.removedLineBackground': '#f8514918',
    'diffEditor.removedTextBackground': '#f8514930',
    'editorWidget.background': '#16181d',
    'editorWidget.border': '#272a33',
  },
});

monaco.editor.defineTheme('optlens-light', {
  base: 'vs',
  inherit: true,
  rules: shared(false),
  colors: {
    'editor.background': '#ffffff',
    focusBorder: '#00000000',
    'editor.lineHighlightBackground': '#0000000a',
    'editorLineNumber.foreground': '#b6bac3',
    'editorLineNumber.activeForeground': '#555b66',
    'editor.selectionBackground': '#6d5dfc30',
  },
});

loader.config({ monaco });

export { monaco };
