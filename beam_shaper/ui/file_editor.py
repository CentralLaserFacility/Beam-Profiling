import keyword
import re

from PySide6.QtGui import QColor, QFont, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QPlainTextEdit, QVBoxLayout


def _format(colour, bold=False, italic=False):
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(colour))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    fmt.setFontItalic(italic)
    return fmt


class PythonHighlighter(QSyntaxHighlighter):
    # Later rules win where they overlap, so strings and comments come last
    RULES = [
        (r"\b(" + "|".join(keyword.kwlist) + r")\b", _format("#00007f", bold=True)),
        (r"\b(self|None|True|False)\b", _format("#7f007f")),
        (r"\b[0-9]+\.?[0-9]*([eE][-+]?[0-9]+)?\b", _format("#007f7f")),
        (r"\bdef\s+(\w+)", _format("#007f7f", bold=True)),
        (r"\"[^\"\\]*(\\.[^\"\\]*)*\"|'[^'\\]*(\\.[^'\\]*)*'", _format("#7f007f")),
        (r"#[^\n]*", _format("#007f00", italic=True)),
    ]

    def __init__(self, document):
        super().__init__(document)
        self.rules = [(re.compile(pattern), fmt) for pattern, fmt in self.RULES]

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class FileEditDialog(QDialog):
    """Edit a Python file (the user filter or algorithm). Saves on OK."""

    def __init__(self, filename, parent=None):
        super().__init__(parent)
        self.setWindowTitle(filename)
        self.resize(800, 800)
        self.filename = filename

        self.editor = QPlainTextEdit()
        self.editor.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.highlighter = PythonHighlighter(self.editor.document())
        with open(filename) as f:
            self.editor.setPlainText(f.read())

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.editor)
        layout.addWidget(buttons)

    def save(self):
        try:
            with open(self.filename, "w") as f:
                f.write(self.editor.toPlainText())
        except OSError as e:
            QMessageBox.critical(self, "Save error", "Couldn't save the file:\n\n{0}".format(e))
            return
        self.accept()
