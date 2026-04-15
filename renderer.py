import math
from typing import Dict, List, Tuple

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from math3d import EPS, Camera, Object3D, Vec3, apply_euler, clamp


class RenderWidget(QWidget):
    def __init__(self, objects: List[Object3D], camera: Camera) -> None:
        super().__init__()
        self.setMinimumSize(900, 650)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.objects = objects
        self.camera = camera
        self.light_pos = Vec3(0.0, 4.0, -2.0)
        self.render_mode = "wireframe"
        self.show_edges = True
        self.show_normals = False
        self.show_local_axes = False
        self.background = QColor(18, 20, 24)
        self.selected_index = 0
        self.move_step_value = 0.4
        self.rot_step_value = 8.0
        self.object_rotate_sens = 0.05
        self.object_move_sens = 0.008
        self.camera_rotate_sens = 0.28
        self.camera_pan_sens = 0.0018
        self.camera_zoom_sens = 0.14
        self._last_mouse_pos: QPoint | None = None
        self._drag_mode: str | None = None
        self.orbit_target = self.scene_center()
        self.orbit_distance = 10.0
        self.orbit_yaw = 0.0
        self.orbit_pitch = 0.0
        self.sync_orbit_from_camera()

    def set_render_mode(self, mode: str) -> None:
        self.render_mode = mode
        self.update()

    def set_show_edges(self, enabled: bool) -> None:
        self.show_edges = enabled
        self.update()

    def set_show_normals(self, enabled: bool) -> None:
        self.show_normals = enabled
        self.update()

    def set_show_local_axes(self, enabled: bool) -> None:
        self.show_local_axes = enabled
        self.update()

    def set_light_position(self, pos: Vec3) -> None:
        self.light_pos = pos
        self.update()

    def set_selected_index(self, idx: int) -> None:
        self.selected_index = int(clamp(idx, 0, max(0, len(self.objects) - 1)))

    def set_steps(self, move_step: float, rot_step: float) -> None:
        self.move_step_value = move_step
        self.rot_step_value = rot_step

    def selected_object(self) -> Object3D:
        return self.objects[self.selected_index]

    def scene_center(self) -> Vec3:
        all_points: List[Vec3] = []
        for obj in self.objects:
            all_points.extend(obj.world_vertices())
        if not all_points:
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(
            sum(p.x for p in all_points) / len(all_points),
            sum(p.y for p in all_points) / len(all_points),
            sum(p.z for p in all_points) / len(all_points),
        )

    def _camera_forward(self) -> Vec3:
        return apply_euler(Vec3(0.0, 0.0, 1.0), self.camera.rotation).normalized()

    def _camera_right(self) -> Vec3:
        return apply_euler(Vec3(1.0, 0.0, 0.0), self.camera.rotation).normalized()

    def _camera_up(self) -> Vec3:
        return apply_euler(Vec3(0.0, 1.0, 0.0), self.camera.rotation).normalized()

    def sync_orbit_from_camera(self) -> None:
        self.orbit_yaw = self.camera.rotation.y
        self.orbit_pitch = clamp(-self.camera.rotation.x, -88.0, 88.0)
        view_dir = self._camera_forward()
        to_target = self.orbit_target - self.camera.position
        projected = to_target.dot(view_dir)
        if projected > 0.2:
            self.orbit_distance = projected
        else:
            self.orbit_distance = max(1.0, to_target.length())

    def apply_orbit_camera(self) -> None:
        self.orbit_pitch = clamp(self.orbit_pitch, -88.0, 88.0)
        self.orbit_distance = clamp(self.orbit_distance, 0.6, 200.0)
        yaw = math.radians(self.orbit_yaw)
        pitch = math.radians(self.orbit_pitch)
        cos_pitch = math.cos(pitch)
        forward = Vec3(math.sin(yaw) * cos_pitch, math.sin(pitch), math.cos(yaw) * cos_pitch).normalized()
        self.camera.rotation = Vec3(-self.orbit_pitch, self.orbit_yaw, 0.0)
        self.camera.position = self.orbit_target - forward * self.orbit_distance

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.setFocus()
        self._last_mouse_pos = event.pos()
        modifiers = event.modifiers()
        if event.button() == Qt.LeftButton:
            if modifiers & Qt.ControlModifier:
                self._drag_mode = "object_move"
            elif modifiers & Qt.ShiftModifier:
                self._drag_mode = "camera_rotate"
            else:
                self._drag_mode = "object_rotate"
        elif event.button() == Qt.RightButton:
            self._drag_mode = "camera_rotate"
        elif event.button() == Qt.MiddleButton:
            self._drag_mode = "camera_move"
        else:
            self._drag_mode = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._last_mouse_pos is None or self._drag_mode is None:
            super().mouseMoveEvent(event)
            return

        current = event.pos()
        dx = current.x() - self._last_mouse_pos.x()
        dy = current.y() - self._last_mouse_pos.y()
        self._last_mouse_pos = current

        if dx == 0 and dy == 0:
            super().mouseMoveEvent(event)
            return

        obj_rot_factor = max(0.12, self.rot_step_value * self.object_rotate_sens)
        obj_move_factor = max(0.0015, self.move_step_value * self.object_move_sens)

        if self._drag_mode == "object_rotate":
            obj = self.selected_object()
            obj.rotation = obj.rotation + Vec3(dy * obj_rot_factor, dx * obj_rot_factor, 0.0)
        elif self._drag_mode == "object_move":
            obj = self.selected_object()
            right = self._camera_right()
            up = self._camera_up()
            obj.position = obj.position + right * (dx * obj_move_factor) + up * (-dy * obj_move_factor)
        elif self._drag_mode == "camera_rotate":
            self.orbit_yaw += dx * self.camera_rotate_sens
            self.orbit_pitch += -dy * self.camera_rotate_sens
            self.apply_orbit_camera()
        elif self._drag_mode == "camera_move":
            pan_scale = max(0.0008, self.orbit_distance * self.camera_pan_sens)
            right = self._camera_right()
            up = self._camera_up()
            offset = right * (-dx * pan_scale) + up * (dy * pan_scale)
            self.orbit_target = self.orbit_target + offset
            self.camera.position = self.camera.position + offset

        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._last_mouse_pos = None
        self._drag_mode = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        delta = event.angleDelta().y() / 120.0
        if abs(delta) < EPS:
            super().wheelEvent(event)
            return

        zoom = self.move_step_value * 0.55 * delta
        if event.modifiers() & Qt.ShiftModifier:
            zoom_factor = 1.0 - delta * self.camera_zoom_sens
            zoom_factor = clamp(zoom_factor, 0.70, 1.30)
            self.orbit_distance *= zoom_factor
            self.apply_orbit_camera()
        else:
            obj = self.selected_object()
            forward = self._camera_forward()
            obj.position = obj.position + forward * zoom
        self.update()
        super().wheelEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background)

        geometry = self.collect_geometry()
        if self.render_mode == "wireframe":
            self.draw_wireframe(painter, geometry)
        else:
            image = self.render_raster(geometry)
            painter.drawImage(0, 0, image)
            if self.show_edges:
                self.draw_wireframe(painter, geometry, overlay=True)

        self.draw_axis(painter)
        self.draw_light_marker(painter)
        if self.show_local_axes:
            self.draw_objects_local_axes(painter)
        if self.show_normals:
            self.draw_normals(painter, geometry)
        painter.end()

    def project(self, p_camera: Vec3) -> Tuple[float, float, float] | None:
        if p_camera.z <= self.camera.near:
            return None
        w = max(1, self.width())
        h = max(1, self.height())
        focal = 0.5 * w / math.tan(math.radians(self.camera.fov_deg) * 0.5)
        x = p_camera.x * focal / p_camera.z + w * 0.5
        y = -p_camera.y * focal / p_camera.z + h * 0.5
        return x, y, p_camera.z

    def collect_geometry(self) -> List[Dict]:
        geometry: List[Dict] = []
        for obj in self.objects:
            world_vertices = obj.world_vertices()
            cam_vertices = [self.camera.world_to_camera(v) for v in world_vertices]
            vertex_normals: List[Vec3] = [Vec3(0.0, 0.0, 0.0) for _ in world_vertices]
            face_normals_world: List[Vec3] = []
            face_normals_camera: List[Vec3] = []

            for a, b, c in obj.mesh.faces:
                wa, wb, wc = world_vertices[a], world_vertices[b], world_vertices[c]
                cw_a, cw_b, cw_c = cam_vertices[a], cam_vertices[b], cam_vertices[c]
                n_world = (wb - wa).cross(wc - wa).normalized()
                n_cam = (cw_b - cw_a).cross(cw_c - cw_a).normalized()
                face_normals_world.append(n_world)
                face_normals_camera.append(n_cam)
                vertex_normals[a] = vertex_normals[a] + n_world
                vertex_normals[b] = vertex_normals[b] + n_world
                vertex_normals[c] = vertex_normals[c] + n_world

            vertex_normals = [n.normalized() for n in vertex_normals]
            geometry.append(
                {
                    "object": obj,
                    "world": world_vertices,
                    "camera": cam_vertices,
                    "vertex_normals": vertex_normals,
                    "face_normals_world": face_normals_world,
                    "face_normals_camera": face_normals_camera,
                }
            )
        return geometry

    def draw_wireframe(self, painter: QPainter, geometry: List[Dict], overlay: bool = False) -> None:
        pen = QPen(QColor(220, 220, 220) if not overlay else QColor(15, 15, 15))
        pen.setWidth(1)
        painter.setPen(pen)
        for geom in geometry:
            obj: Object3D = geom["object"]
            cam_vertices: List[Vec3] = geom["camera"]
            projected: List[Tuple[float, float, float] | None] = [self.project(v) for v in cam_vertices]
            for i, j in obj.mesh.edges:
                a = projected[i]
                b = projected[j]
                if a is None or b is None:
                    continue
                painter.drawLine(QPoint(int(a[0]), int(a[1])), QPoint(int(b[0]), int(b[1])))

    def draw_axis(self, painter: QPainter) -> None:
        center_world = Vec3(0.0, 0.0, 0.0)
        axis_len = 2.2
        axis = [
            (Vec3(axis_len, 0.0, 0.0), QColor(220, 90, 90)),
            (Vec3(0.0, axis_len, 0.0), QColor(90, 220, 90)),
            (Vec3(0.0, 0.0, axis_len), QColor(90, 140, 250)),
        ]
        c_cam = self.camera.world_to_camera(center_world)
        c_proj = self.project(c_cam)
        if c_proj is None:
            return
        for axis_end, color in axis:
            e_cam = self.camera.world_to_camera(axis_end)
            e_proj = self.project(e_cam)
            if e_proj is None:
                continue
            painter.setPen(QPen(color, 2))
            painter.drawLine(int(c_proj[0]), int(c_proj[1]), int(e_proj[0]), int(e_proj[1]))

    def draw_light_marker(self, painter: QPainter) -> None:
        p_cam = self.camera.world_to_camera(self.light_pos)
        p = self.project(p_cam)
        if p is None:
            return
        painter.setPen(QPen(QColor(255, 245, 130), 2))
        painter.setBrush(QColor(255, 245, 130))
        painter.drawEllipse(QPoint(int(p[0]), int(p[1])), 5, 5)

    def draw_objects_local_axes(self, painter: QPainter) -> None:
        for obj in self.objects:
            axis_len = max(0.4, max(obj.size.x, obj.size.y, obj.size.z) * 0.9)
            origin = obj.position
            axis_defs = [
                (Vec3(axis_len, 0.0, 0.0), QColor(235, 80, 80)),
                (Vec3(0.0, axis_len, 0.0), QColor(80, 230, 80)),
                (Vec3(0.0, 0.0, axis_len), QColor(70, 140, 250)),
            ]
            c_cam = self.camera.world_to_camera(origin)
            c_proj = self.project(c_cam)
            if c_proj is None:
                continue
            for axis, color in axis_defs:
                end_world = origin + apply_euler(axis, obj.rotation)
                e_cam = self.camera.world_to_camera(end_world)
                e_proj = self.project(e_cam)
                if e_proj is None:
                    continue
                painter.setPen(QPen(color, 2))
                painter.drawLine(int(c_proj[0]), int(c_proj[1]), int(e_proj[0]), int(e_proj[1]))

    def draw_normals(self, painter: QPainter, geometry: List[Dict]) -> None:
        painter.setPen(QPen(QColor(250, 250, 180), 1))
        for data in geometry:
            world_vertices: List[Vec3] = data["world"]
            face_normals: List[Vec3] = data["face_normals_world"]
            obj: Object3D = data["object"]
            normal_len = max(0.2, max(obj.size.x, obj.size.y, obj.size.z) * 0.18)
            for face_idx, (a, b, c) in enumerate(obj.mesh.faces):
                p0, p1, p2 = world_vertices[a], world_vertices[b], world_vertices[c]
                center = (p0 + p1 + p2) * (1.0 / 3.0)
                normal = face_normals[face_idx]
                end = center + normal * normal_len
                c_proj = self.project(self.camera.world_to_camera(center))
                e_proj = self.project(self.camera.world_to_camera(end))
                if c_proj is None or e_proj is None:
                    continue
                painter.drawLine(int(c_proj[0]), int(c_proj[1]), int(e_proj[0]), int(e_proj[1]))

    def render_raster(self, geom: List[Dict]) -> QImage:
        w = max(1, self.width())
        h = max(1, self.height())
        img = QImage(w, h, QImage.Format_RGB32)
        img.fill(self.background)
        z_buffer: List[float] = [float("inf")] * (w * h)
        triangles: List[Dict] = []

        for data in geom:
            obj: Object3D = data["object"]
            world_vertices: List[Vec3] = data["world"]
            cam_vertices: List[Vec3] = data["camera"]
            v_normals: List[Vec3] = data["vertex_normals"]
            f_normals_world: List[Vec3] = data["face_normals_world"]
            f_normals_camera: List[Vec3] = data["face_normals_camera"]

            for face_idx, (a, b, c) in enumerate(obj.mesh.faces):
                ca, cb, cc = cam_vertices[a], cam_vertices[b], cam_vertices[c]
                centroid = (ca + cb + cc) * (1.0 / 3.0)
                normal_cam = f_normals_camera[face_idx]
                if normal_cam.dot(centroid) >= 0.0:
                    continue
                pa, pb, pc = self.project(ca), self.project(cb), self.project(cc)
                if pa is None or pb is None or pc is None:
                    continue
                triangles.append(
                    {
                        "object": obj,
                        "proj": (pa, pb, pc),
                        "cam": (ca, cb, cc),
                        "world": (world_vertices[a], world_vertices[b], world_vertices[c]),
                        "face_normal_world": f_normals_world[face_idx],
                        "vertex_normals": (v_normals[a], v_normals[b], v_normals[c]),
                    }
                )

        for tri in triangles:
            self.raster_triangle(img, z_buffer, tri)
        return img

    def shade_intensity(self, world_pos: Vec3, normal_world: Vec3) -> float:
        light_dir = (self.light_pos - world_pos).normalized()
        diffuse = max(0.0, normal_world.normalized().dot(light_dir))
        ambient = 0.2
        return clamp(ambient + 0.8 * diffuse, 0.0, 1.0)

    def color_with_intensity(self, base: QColor, intensity: float) -> QColor:
        return QColor(
            int(clamp(base.red() * intensity, 0.0, 255.0)),
            int(clamp(base.green() * intensity, 0.0, 255.0)),
            int(clamp(base.blue() * intensity, 0.0, 255.0)),
        )

    def raster_triangle(self, img: QImage, z_buffer: List[float], tri: Dict) -> None:
        w = img.width()
        h = img.height()
        p0, p1, p2 = tri["proj"]
        w0, w1, w2 = tri["world"]
        z0, z1, z2 = tri["cam"]
        x0, y0, dz0 = p0
        x1, y1, dz1 = p1
        x2, y2, dz2 = p2

        min_x = max(0, int(math.floor(min(x0, x1, x2))))
        max_x = min(w - 1, int(math.ceil(max(x0, x1, x2))))
        min_y = max(0, int(math.floor(min(y0, y1, y2))))
        max_y = min(h - 1, int(math.ceil(max(y0, y1, y2))))
        if min_x > max_x or min_y > max_y:
            return

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < EPS:
            return

        obj: Object3D = tri["object"]
        face_n = tri["face_normal_world"].normalized()
        vn0, vn1, vn2 = tri["vertex_normals"]
        i0 = i1 = i2 = 1.0
        if self.render_mode == "gouraud":
            i0 = self.shade_intensity(w0, vn0)
            i1 = self.shade_intensity(w1, vn1)
            i2 = self.shade_intensity(w2, vn2)

        for py in range(min_y, max_y + 1):
            for px in range(min_x, max_x + 1):
                sx = px + 0.5
                sy = py + 0.5
                a = ((y1 - y2) * (sx - x2) + (x2 - x1) * (sy - y2)) / denom
                b = ((y2 - y0) * (sx - x2) + (x0 - x2) * (sy - y2)) / denom
                c = 1.0 - a - b
                if a < -EPS or b < -EPS or c < -EPS:
                    continue
                depth = a * dz0 + b * dz1 + c * dz2
                idx = py * w + px
                if depth >= z_buffer[idx]:
                    continue
                z_buffer[idx] = depth

                if self.render_mode == "hidden":
                    color = obj.color
                elif self.render_mode == "flat":
                    wp = w0 * a + w1 * b + w2 * c
                    color = self.color_with_intensity(obj.color, self.shade_intensity(wp, face_n))
                elif self.render_mode == "gouraud":
                    color = self.color_with_intensity(obj.color, clamp(a * i0 + b * i1 + c * i2, 0.0, 1.0))
                elif self.render_mode == "phong":
                    wp = w0 * a + w1 * b + w2 * c
                    n = (vn0 * a + vn1 * b + vn2 * c).normalized()
                    color = self.color_with_intensity(obj.color, self.shade_intensity(wp, n))
                else:
                    color = obj.color
                img.setPixelColor(px, py, color)
