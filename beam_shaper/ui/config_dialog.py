from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from beam_shaper.core.config import AppConfig


class ConfigDialog(QDialog):
    """Edits an AppConfig. When accepted, the config is updated and saved to filename."""

    def __init__(self, config, filename="./config.ini", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Beam profiling configuration")
        self.config = config
        self.filename = filename

        # One widget per config option, chosen by the option's type
        form = QFormLayout()
        self.widgets = {}
        for option in AppConfig.options():
            value = getattr(config, option.name)
            choices = option.metadata["choices"]
            if option.type is bool:
                widget = QCheckBox()
                widget.setChecked(value)
            elif choices:
                widget = QComboBox()
                widget.addItems(list(choices))
                widget.setCurrentText(value)
            else:
                widget = QLineEdit(str(value))
            widget.setObjectName(option.name)
            self.widgets[option.name] = widget
            form.addRow(option.metadata["label"], widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def value_text(self, name):
        widget = self.widgets[name]
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text()

    def apply(self):
        edited = AppConfig(**vars(self.config))
        for option in AppConfig.options():
            try:
                edited.set_from_string(option.name, self.value_text(option.name))
            except ValueError as e:
                QMessageBox.critical(
                    self, "Invalid value", "{0}: {1}".format(option.metadata["label"], e)
                )
                return
        vars(self.config).update(vars(edited))
        self.config.save(self.filename)
        self.config.ensure_diag_folder()
        self.accept()
