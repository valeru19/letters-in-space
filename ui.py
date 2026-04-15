import json
import math
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from math3d import Camera, Object3D, Vec3, build_default_objects
from renderer import RenderWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ЛР2: 3D буквы О и В (PySide)")
        self.camera = Camera()
        self.objects = build_default_objects()
        self.canvas = RenderWidget(self.objects, self.camera)
        self.canvas.setFocusPolicy(Qt.StrongFocus)

        controls = self.build_controls()
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(controls)
        self.setCentralWidget(central)
        self.resize(1400, 820)

    def current_object(self) -> Object3D:
        return self.objects[self.object_selector.currentIndex()]

    def build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(420)
        root = QVBoxLayout(panel)
        title = QLabel("Управление сценой")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)

        self.object_selector = QComboBox()
        self.object_selector.addItems([obj.name for obj in self.objects])
        self.object_selector.currentIndexChanged.connect(self.sync_object_fields)
        root.addWidget(QLabel("Выбор буквы"))
        root.addWidget(self.object_selector)

        params_group = QGroupBox("Параметры буквы")
        params_form = QFormLayout(params_group)
        self.width_box = self.make_spin(0.2, 5.0, 0.1, 1.0)
        self.height_box = self.make_spin(0.2, 6.0, 0.1, 1.0)
        self.depth_box = self.make_spin(0.2, 5.0, 0.1, 1.0)
        self.width_box.valueChanged.connect(self.apply_size)
        self.height_box.valueChanged.connect(self.apply_size)
        self.depth_box.valueChanged.connect(self.apply_size)
        params_form.addRow("Ширина", self.width_box)
        params_form.addRow("Высота", self.height_box)
        params_form.addRow("Глубина", self.depth_box)

        color_row = QHBoxLayout()
        self.color_btn = QPushButton("Выбрать цвет")
        self.color_btn.clicked.connect(self.pick_object_color)
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(40, 20)
        self.color_preview.setStyleSheet("border: 1px solid #666;")
        color_row.addWidget(self.color_btn)
        color_row.addWidget(self.color_preview)
        params_form.addRow("Цвет", color_row)
        root.addWidget(params_group)

        step_group = QGroupBox("Шаги преобразований")
        step_form = QFormLayout(step_group)
        self.move_step = self.make_spin(0.05, 5.0, 0.05, 0.4)
        self.rot_step = self.make_spin(1.0, 45.0, 1.0, 8.0)
        self.move_step.valueChanged.connect(self.sync_canvas_steps)
        self.rot_step.valueChanged.connect(self.sync_canvas_steps)
        step_form.addRow("Смещение", self.move_step)
        step_form.addRow("Поворот (град.)", self.rot_step)
        root.addWidget(step_group)

        object_group = QGroupBox("Преобразования буквы")
        object_layout = QVBoxLayout(object_group)
        object_layout.addLayout(self.make_move_buttons(self.move_selected))
        object_layout.addLayout(self.make_rot_buttons(self.rotate_selected))
        reflection_row = QHBoxLayout()
        for axis in ("X", "Y", "Z"):
            btn = QPushButton(f"Отразить {axis}")
            btn.clicked.connect(lambda _, ax=axis.lower(): self.reflect_selected(ax))
            reflection_row.addWidget(btn)
        object_layout.addLayout(reflection_row)
        root.addWidget(object_group)

        camera_group = QGroupBox("Камера")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.addLayout(self.make_move_buttons(self.move_camera))
        camera_layout.addLayout(self.make_rot_buttons(self.rotate_camera))
        auto_btn = QPushButton("Автомасштаб")
        auto_btn.clicked.connect(self.auto_scale)
        camera_layout.addWidget(auto_btn)
        root.addWidget(camera_group)

        render_group = QGroupBox("Рендер и отладка")
        render_form = QFormLayout(render_group)
        self.mode_selector = QComboBox()
        self.mode_selector.addItem("Каркас", "wireframe")
        self.mode_selector.addItem("Видимые части (Z-буфер)", "hidden")
        self.mode_selector.addItem("Монотонная (Flat)", "flat")
        self.mode_selector.addItem("Гуро", "gouraud")
        self.mode_selector.addItem("Фонг", "phong")
        self.mode_selector.currentIndexChanged.connect(self.apply_mode)
        self.edge_check = QCheckBox("Рёбра поверх заливки")
        self.edge_check.setChecked(True)
        self.edge_check.stateChanged.connect(lambda _: self.canvas.set_show_edges(self.edge_check.isChecked()))
        self.normals_check = QCheckBox("Показывать нормали")
        self.normals_check.stateChanged.connect(lambda _: self.canvas.set_show_normals(self.normals_check.isChecked()))
        self.local_axes_check = QCheckBox("Показывать локальные оси объектов")
        self.local_axes_check.stateChanged.connect(
            lambda _: self.canvas.set_show_local_axes(self.local_axes_check.isChecked())
        )
        render_form.addRow("Режим", self.mode_selector)
        render_form.addRow("", self.edge_check)
        render_form.addRow("", self.normals_check)
        render_form.addRow("", self.local_axes_check)
        root.addWidget(render_group)

        light_group = QGroupBox("Источник света")
        light_form = QFormLayout(light_group)
        self.light_x = self.make_spin(-20.0, 20.0, 0.2, 0.0)
        self.light_y = self.make_spin(-20.0, 20.0, 0.2, 4.0)
        self.light_z = self.make_spin(-20.0, 20.0, 0.2, -2.0)
        self.light_x.valueChanged.connect(self.apply_light)
        self.light_y.valueChanged.connect(self.apply_light)
        self.light_z.valueChanged.connect(self.apply_light)
        light_form.addRow("X", self.light_x)
        light_form.addRow("Y", self.light_y)
        light_form.addRow("Z", self.light_z)
        root.addWidget(light_group)

        scene_group = QGroupBox("Сцена")
        scene_layout = QHBoxLayout(scene_group)
        save_btn = QPushButton("Сохранить JSON")
        load_btn = QPushButton("Загрузить JSON")
        save_btn.clicked.connect(self.save_scene)
        load_btn.clicked.connect(self.load_scene)
        scene_layout.addWidget(save_btn)
        scene_layout.addWidget(load_btn)
        root.addWidget(scene_group)

        hint = QLabel(
            "Клавиши:\n"
            "Стрелки/W/S - смещение буквы\n"
            "Q/E/A/D/Z/C - поворот буквы\n"
            "Shift + те же клавиши - камера\n\n"
            "Мышь на холсте:\n"
            "ЛКМ - вращение выбранной буквы\n"
            "Ctrl + ЛКМ - перемещение буквы\n"
            "ПКМ или Shift + ЛКМ - орбита камеры\n"
            "Средняя кнопка - панорамирование\n"
            "Колесо - зум буквы (Shift + колесо - камера)"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

        self.sync_object_fields()
        self.sync_canvas_steps()
        self.apply_mode()
        self.apply_light()
        return panel

    def make_spin(self, low: float, high: float, step: float, value: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(low, high)
        box.setSingleStep(step)
        box.setValue(value)
        return box

    def make_move_buttons(self, callback):
        row = QHBoxLayout()
        for text, direction in (
            ("X-", Vec3(-1, 0, 0)),
            ("X+", Vec3(1, 0, 0)),
            ("Y-", Vec3(0, -1, 0)),
            ("Y+", Vec3(0, 1, 0)),
            ("Z-", Vec3(0, 0, -1)),
            ("Z+", Vec3(0, 0, 1)),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, d=direction: callback(d))
            row.addWidget(btn)
        return row

    def make_rot_buttons(self, callback):
        row = QHBoxLayout()
        for text, axis in (
            ("Rx-", Vec3(-1, 0, 0)),
            ("Rx+", Vec3(1, 0, 0)),
            ("Ry-", Vec3(0, -1, 0)),
            ("Ry+", Vec3(0, 1, 0)),
            ("Rz-", Vec3(0, 0, -1)),
            ("Rz+", Vec3(0, 0, 1)),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, a=axis: callback(a))
            row.addWidget(btn)
        return row

    def apply_mode(self) -> None:
        self.canvas.set_render_mode(self.mode_selector.currentData())

    def apply_light(self) -> None:
        self.canvas.set_light_position(Vec3(self.light_x.value(), self.light_y.value(), self.light_z.value()))

    def sync_object_fields(self) -> None:
        self.canvas.set_selected_index(self.object_selector.currentIndex())
        obj = self.current_object()
        for box, value in ((self.width_box, obj.size.x), (self.height_box, obj.size.y), (self.depth_box, obj.size.z)):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)
        self.update_color_preview(obj.color)
        self.canvas.update()

    def sync_canvas_steps(self) -> None:
        self.canvas.set_steps(self.move_step.value(), self.rot_step.value())

    def update_color_preview(self, color: QColor) -> None:
        self.color_preview.setStyleSheet(
            f"border: 1px solid #666; background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
        )

    def pick_object_color(self) -> None:
        obj = self.current_object()
        color = QColorDialog.getColor(obj.color, self, f"Цвет буквы {obj.name}")
        if not color.isValid():
            return
        obj.color = color
        self.update_color_preview(color)
        self.canvas.update()

    def apply_size(self) -> None:
        obj = self.current_object()
        obj.size = Vec3(self.width_box.value(), self.height_box.value(), self.depth_box.value())
        self.canvas.update()

    def move_selected(self, direction: Vec3) -> None:
        self.current_object().position = self.current_object().position + direction * self.move_step.value()
        self.canvas.update()

    def rotate_selected(self, axis: Vec3) -> None:
        self.current_object().rotation = self.current_object().rotation + axis * self.rot_step.value()
        self.canvas.update()

    def reflect_selected(self, axis: str) -> None:
        self.current_object().reflect(axis)
        self.canvas.update()

    def move_camera(self, direction: Vec3) -> None:
        self.camera.position = self.camera.position + direction * self.move_step.value()
        self.canvas.sync_orbit_from_camera()
        self.canvas.update()

    def rotate_camera(self, axis: Vec3) -> None:
        self.camera.rotation = self.camera.rotation + axis * self.rot_step.value()
        self.canvas.sync_orbit_from_camera()
        self.canvas.update()

    def auto_scale(self) -> None:
        all_vertices: List[Vec3] = []
        for obj in self.objects:
            all_vertices.extend(obj.world_vertices())
        if not all_vertices:
            return
        center = Vec3(
            sum(v.x for v in all_vertices) / len(all_vertices),
            sum(v.y for v in all_vertices) / len(all_vertices),
            sum(v.z for v in all_vertices) / len(all_vertices),
        )
        radius = max((v - center).length() for v in all_vertices)
        radius = max(radius, 0.5)
        dist = radius / math.tan(math.radians(self.camera.fov_deg) * 0.5) + radius * 0.7
        self.camera.position = Vec3(center.x, center.y, center.z - dist)
        self.camera.rotation = Vec3(0.0, 0.0, 0.0)
        self.canvas.orbit_target = center
        self.canvas.sync_orbit_from_camera()
        self.canvas.update()

    def scene_to_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "camera": {
                "position": self.camera.position.to_list(),
                "rotation": self.camera.rotation.to_list(),
                "fov_deg": self.camera.fov_deg,
                "near": self.camera.near,
                "orbit_target": self.canvas.orbit_target.to_list(),
                "orbit_distance": self.canvas.orbit_distance,
                "orbit_yaw": self.canvas.orbit_yaw,
                "orbit_pitch": self.canvas.orbit_pitch,
            },
            "light": self.canvas.light_pos.to_list(),
            "render": {
                "mode": self.mode_selector.currentData(),
                "show_edges": self.edge_check.isChecked(),
                "show_normals": self.normals_check.isChecked(),
                "show_local_axes": self.local_axes_check.isChecked(),
            },
            "steps": {"move": self.move_step.value(), "rotate": self.rot_step.value()},
            "objects": [
                {
                    "name": obj.name,
                    "size": obj.size.to_list(),
                    "position": obj.position.to_list(),
                    "rotation": obj.rotation.to_list(),
                    "mirror": obj.mirror.to_list(),
                    "color": [obj.color.red(), obj.color.green(), obj.color.blue()],
                }
                for obj in self.objects
            ],
        }

    def apply_scene_dict(self, data: Dict[str, Any]) -> None:
        cam = data.get("camera", {})
        self.camera.position = Vec3.from_list(cam.get("position", self.camera.position.to_list()))
        self.camera.rotation = Vec3.from_list(cam.get("rotation", self.camera.rotation.to_list()))
        self.camera.fov_deg = float(cam.get("fov_deg", self.camera.fov_deg))
        self.camera.near = float(cam.get("near", self.camera.near))
        self.canvas.orbit_target = Vec3.from_list(cam.get("orbit_target", self.canvas.orbit_target.to_list()))
        self.canvas.orbit_distance = float(cam.get("orbit_distance", self.canvas.orbit_distance))
        self.canvas.orbit_yaw = float(cam.get("orbit_yaw", self.canvas.orbit_yaw))
        self.canvas.orbit_pitch = float(cam.get("orbit_pitch", self.canvas.orbit_pitch))
        self.canvas.sync_orbit_from_camera()

        self.canvas.light_pos = Vec3.from_list(data.get("light", self.canvas.light_pos.to_list()))
        self.light_x.setValue(self.canvas.light_pos.x)
        self.light_y.setValue(self.canvas.light_pos.y)
        self.light_z.setValue(self.canvas.light_pos.z)

        render = data.get("render", {})
        mode = render.get("mode", "wireframe")
        idx = max(0, self.mode_selector.findData(mode))
        self.mode_selector.setCurrentIndex(idx)
        self.edge_check.setChecked(bool(render.get("show_edges", True)))
        self.normals_check.setChecked(bool(render.get("show_normals", False)))
        self.local_axes_check.setChecked(bool(render.get("show_local_axes", False)))

        steps = data.get("steps", {})
        self.move_step.setValue(float(steps.get("move", self.move_step.value())))
        self.rot_step.setValue(float(steps.get("rotate", self.rot_step.value())))

        objects_by_name = {obj.name: obj for obj in self.objects}
        for item in data.get("objects", []):
            obj = objects_by_name.get(item.get("name", ""))
            if obj is None:
                continue
            obj.size = Vec3.from_list(item.get("size", obj.size.to_list()))
            obj.position = Vec3.from_list(item.get("position", obj.position.to_list()))
            obj.rotation = Vec3.from_list(item.get("rotation", obj.rotation.to_list()))
            obj.mirror = Vec3.from_list(item.get("mirror", obj.mirror.to_list()))
            c = item.get("color", [obj.color.red(), obj.color.green(), obj.color.blue()])
            if isinstance(c, list) and len(c) == 3:
                obj.color = QColor(int(c[0]), int(c[1]), int(c[2]))

        self.sync_object_fields()
        self.sync_canvas_steps()
        self.apply_light()
        self.canvas.update()

    def save_scene(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить сцену",
            str(Path.cwd() / "scene.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.scene_to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))
            return
        QMessageBox.information(self, "Сцена сохранена", f"Файл: {path}")

    def load_scene(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить сцену", str(Path.cwd()), "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Неверный формат JSON")
            self.apply_scene_dict(data)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Ошибка загрузки", str(exc))
            return
        QMessageBox.information(self, "Сцена загружена", f"Файл: {path}")

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        move = self.move_step.value()
        rot = self.rot_step.value()
        use_camera = bool(event.modifiers() & Qt.ShiftModifier)
        target_pos = self.camera if use_camera else self.current_object()
        target_rot = self.camera if use_camera else self.current_object()

        if event.key() == Qt.Key_Left:
            target_pos.position = target_pos.position + Vec3(-move, 0.0, 0.0)
        elif event.key() == Qt.Key_Right:
            target_pos.position = target_pos.position + Vec3(move, 0.0, 0.0)
        elif event.key() == Qt.Key_Up:
            target_pos.position = target_pos.position + Vec3(0.0, move, 0.0)
        elif event.key() == Qt.Key_Down:
            target_pos.position = target_pos.position + Vec3(0.0, -move, 0.0)
        elif event.key() == Qt.Key_W:
            target_pos.position = target_pos.position + Vec3(0.0, 0.0, move)
        elif event.key() == Qt.Key_S:
            target_pos.position = target_pos.position + Vec3(0.0, 0.0, -move)
        elif event.key() == Qt.Key_Q:
            target_rot.rotation = target_rot.rotation + Vec3(0.0, -rot, 0.0)
        elif event.key() == Qt.Key_E:
            target_rot.rotation = target_rot.rotation + Vec3(0.0, rot, 0.0)
        elif event.key() == Qt.Key_A:
            target_rot.rotation = target_rot.rotation + Vec3(rot, 0.0, 0.0)
        elif event.key() == Qt.Key_D:
            target_rot.rotation = target_rot.rotation + Vec3(-rot, 0.0, 0.0)
        elif event.key() == Qt.Key_Z:
            target_rot.rotation = target_rot.rotation + Vec3(0.0, 0.0, -rot)
        elif event.key() == Qt.Key_C:
            target_rot.rotation = target_rot.rotation + Vec3(0.0, 0.0, rot)
        else:
            super().keyPressEvent(event)
            return
        if use_camera:
            self.canvas.sync_orbit_from_camera()
        self.canvas.update()
