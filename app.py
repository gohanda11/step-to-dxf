#!/usr/bin/env python3
"""
STEP to DXF Web Application
Flask backend with Three.js frontend
"""

from flask import Flask, request, jsonify, render_template, send_file, after_this_request
import os
import json
import tempfile
from werkzeug.utils import secure_filename
import uuid

try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.gp import gp_Pnt
    HAS_PYTHONOCC = True
except ImportError:
    HAS_PYTHONOCC = False

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Add CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Global storage for current session data
sessions = {}

class STEPProcessor:
    """STEP file processing class"""
    
    def __init__(self):
        self.step_shape = None
        self.faces = []
        self.face_data = []
    
    def load_step_file(self, file_path):
        """Load STEP file and extract faces"""
        if not HAS_PYTHONOCC:
            # Fallback: Parse STEP file manually for basic geometry
            return self.parse_step_file_manually(file_path)
        
        try:
            step_reader = STEPControl_Reader()
            status = step_reader.ReadFile(file_path)
            
            if status != 1:  # IFSelect_RetDone
                raise Exception("Failed to read STEP file")
            
            step_reader.TransferRoots()
            self.step_shape = step_reader.OneShape()
            
            # Extract faces
            self.extract_faces()
            
            return {
                'success': True,
                'face_count': len(self.faces),
                'faces': self.face_data
            }
            
        except Exception as e:
            raise Exception(f"Error processing STEP file: {str(e)}")
    
    def parse_step_file_manually(self, file_path):
        """Manually parse STEP file for basic geometry extraction"""
        try:
            with open(file_path, 'r') as file:
                content = file.read()
            
            # Basic STEP parsing - look for geometric entities
            lines = content.split('\n')
            faces_found = 0
            circles_found = 0
            lines_found = 0
            
            for line in lines:
                line = line.strip()
                if 'FACE' in line.upper():
                    faces_found += 1
                elif 'CIRCLE' in line.upper():
                    circles_found += 1
                elif 'LINE' in line.upper():
                    lines_found += 1
            
            # Create mock face data for demonstration
            self.faces = []
            self.face_data = []
            
            # Generate some basic geometric shapes for testing
            face_count = max(faces_found, 3)  # At least 3 faces for demo
            
            for i in range(face_count):
                # Create basic rectangular face data
                vertices = [
                    [-10 + i*5, -10 + i*5, 0],
                    [10 + i*5, -10 + i*5, 0],
                    [10 + i*5, 10 + i*5, 0],
                    [-10 + i*5, 10 + i*5, 0]
                ]
                
                triangles = [
                    [0, 1, 2],
                    [0, 2, 3]
                ]
                
                face_info = {
                    'id': i,
                    'type': 'Plane',
                    'is_plane': True,
                    'mesh': {
                        'vertices': vertices,
                        'triangles': triangles
                    }
                }
                
                self.face_data.append(face_info)
                self.faces.append(f"mock_face_{i}")
            
            return {
                'success': True,
                'face_count': len(self.faces),
                'faces': self.face_data,
                'note': 'Using simplified STEP parsing (pythonocc-core not available)'
            }
            
        except Exception as e:
            raise Exception(f"Error parsing STEP file: {str(e)}")
    
    def export_face_to_dxf(self, face_id):
        """Export face to DXF - Main entry point"""
        if not HAS_EZDXF:
            raise Exception("ezdxf is required for DXF export")
        
        if face_id >= len(self.face_data):
            raise Exception("Invalid face ID")
        
        print(f"Creating DXF for face {face_id}")
        return self.create_new_dxf(face_id)
    
    def export_face_to_svg(self, face_id):
        """Export face to SVG format"""
        if face_id >= len(self.face_data):
            raise Exception("Invalid face ID")
        
        print(f"Creating SVG for face {face_id}")
        return self.create_svg(face_id)
    
    def extract_faces(self):
        """Extract faces from STEP shape"""
        self.faces = []
        self.face_data = []
        
        # First create mesh for entire shape
        shape_mesh = BRepMesh_IncrementalMesh(self.step_shape, 0.1, False, 0.5, True)
        shape_mesh.Perform()
        
        explorer = TopExp_Explorer(self.step_shape, TopAbs_FACE)
        face_index = 0
        
        while explorer.More():
            face = explorer.Current()
            self.faces.append(face)
            
            # Analyze face properties
            try:
                adaptor = BRepAdaptor_Surface(face)
                surface_type = adaptor.GetType()
                is_plane = surface_type == GeomAbs_Plane
                face_type = "Plane" if is_plane else "Curved"
            except:
                face_type = "Unknown"
                is_plane = False
            
            # Get face geometry for visualization
            mesh_data = self.get_face_mesh(face, face_index)
            
            # Get face normal for camera positioning
            try:
                normal = self.get_face_normal(face_index)
            except:
                normal = [0, 0, 1]  # Default normal if calculation fails
            
            face_info = {
                'id': face_index,
                'type': face_type,
                'is_plane': is_plane,
                'mesh': mesh_data,
                'normal': normal
            }
            
            self.face_data.append(face_info)
            face_index += 1
            explorer.Next()
    
    def get_face_mesh(self, face, face_id):
        """Get mesh data for face visualization"""
        try:
            from OCC.Core.TopLoc import TopLoc_Location
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.Poly import Poly_Triangulation
            
            # Create high-quality mesh
            mesh = BRepMesh_IncrementalMesh(face, 0.1, False, 0.5, True)
            mesh.Perform()
            
            # Get triangulation from the face
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation(face, location)
            
            vertices = []
            triangles = []
            
            if triangulation:
                # Extract vertices
                for i in range(1, triangulation.NbNodes() + 1):
                    pnt = triangulation.Node(i)
                    # Apply transformation if needed
                    if not location.IsIdentity():
                        pnt = pnt.Transformed(location.Transformation())
                    vertices.append([pnt.X(), pnt.Y(), pnt.Z()])
                
                # Extract triangles (convert from 1-based to 0-based indexing)
                for i in range(1, triangulation.NbTriangles() + 1):
                    triangle = triangulation.Triangle(i)
                    n1, n2, n3 = triangle.Get()
                    triangles.append([n1-1, n2-1, n3-1])
            
            # Fallback: if no triangulation, create simple representation
            if not vertices:
                from OCC.Core.GProp import GProp_GProps
                from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
                
                props = GProp_GProps()
                brepgprop_SurfaceProperties(face, props)
                center = props.CentreOfMass()
                
                # Get bounding box for better size estimation
                from OCC.Core.Bnd import Bnd_Box
                from OCC.Core.BrepBndLib import brepbndlib_Add
                
                bbox = Bnd_Box()
                brepbndlib_Add(face, bbox)
                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
                
                size_x = max((xmax - xmin) / 2, 1.0)
                size_y = max((ymax - ymin) / 2, 1.0)
                
                vertices = [
                    [center.X() - size_x, center.Y() - size_y, center.Z()],
                    [center.X() + size_x, center.Y() - size_y, center.Z()],
                    [center.X() + size_x, center.Y() + size_y, center.Z()],
                    [center.X() - size_x, center.Y() + size_y, center.Z()]
                ]
                
                triangles = [
                    [0, 1, 2],
                    [0, 2, 3]
                ]
            
            return {
                'vertices': vertices,
                'triangles': triangles
            }
            
        except Exception as e:
            # Fallback: create a default square
            return {
                'vertices': [
                    [-10, -10, 0],
                    [10, -10, 0],
                    [10, 10, 0],
                    [-10, 10, 0]
                ],
                'triangles': [
                    [0, 1, 2],
                    [0, 2, 3]
                ],
                'center': [0, 0, 0]
            }
    
    
    def create_new_dxf(self, face_id):
        """Create DXF from actual face edges (not point cloud)"""
        print(f"Creating DXF from face edges for face {face_id}")
        
        # Create DXF document
        doc = ezdxf.new('R2010')
        doc.units = ezdxf.units.MM
        msp = doc.modelspace()
        
        # Try to use actual STEP geometry if available
        if HAS_PYTHONOCC and hasattr(self, 'step_shape') and self.step_shape and face_id < len(self.faces):
            try:
                return self.create_dxf_from_step_edges(face_id, doc, msp)
            except Exception as e:
                print(f"STEP edge extraction failed: {e}")
                # Fall back to mesh approach
        
        # Fallback: use improved mesh analysis
        return self.create_dxf_from_mesh_improved(face_id, doc, msp)
    
    def create_svg(self, face_id):
        """Create SVG from face geometry"""
        print(f"Creating SVG from face geometry for face {face_id}")
        
        # Try to use actual STEP geometry if available
        if HAS_PYTHONOCC and hasattr(self, 'step_shape') and self.step_shape and face_id < len(self.faces):
            try:
                return self.create_svg_from_step_edges(face_id)
            except Exception as e:
                print(f"STEP edge extraction for SVG failed: {e}")
                # Fall back to mesh approach
        
        # Fallback: use mesh analysis
        return self.create_svg_from_mesh(face_id)
    
    def create_svg_from_step_edges(self, face_id):
        """Extract actual edges from STEP face and convert to SVG"""
        print(f"Extracting STEP edges for SVG for face {face_id}")
        
        try:
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_WIRE
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_BSplineCurve
            from OCC.Core.BRepTools import BRepTools_WireExplorer
            import math
            
            face = self.faces[face_id]
            
            # Store all geometry elements for SVG
            svg_elements = []
            all_points = []  # For bounding box calculation
            
            # First pass: collect all wires and calculate their areas to determine boundary
            from OCC.Core.GProp import GProp_GProps
            from OCC.Core.BRepGProp import brepgprop_LinearProperties
            
            wires = []
            wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            while wire_explorer.More():
                wire = wire_explorer.Current()
                wires.append(wire)
                wire_explorer.Next()
            
            print(f"Found {len(wires)} wires for SVG")
            
            # Determine which wire is the boundary (largest area/perimeter)
            wire_lengths = []
            for i, wire in enumerate(wires):
                try:
                    props = GProp_GProps()
                    brepgprop_LinearProperties(wire, props)
                    length = props.Mass()  # Wire length
                    wire_lengths.append((length, i))
                    print(f"Wire {i+1} length: {length:.2f}")
                except:
                    wire_lengths.append((0, i))
            
            # Sort by length descending - largest wire is usually the boundary
            wire_lengths.sort(reverse=True)
            boundary_wire_idx = wire_lengths[0][1]
            print(f"Wire {boundary_wire_idx+1} identified as boundary")
            
            # Second pass: process wires with correct classification
            for wire_idx, wire in enumerate(wires):
                class_name = 'boundary' if wire_idx == boundary_wire_idx else 'hole'
                print(f"Processing SVG wire {wire_idx+1} - class: {class_name}")
                
                # Process each edge in the wire
                edge_explorer = BRepTools_WireExplorer(wire)
                
                while edge_explorer.More():
                    edge = edge_explorer.Current()
                    
                    try:
                        # Get curve from edge
                        curve, first, last = BRep_Tool.Curve(edge)
                        if curve:
                            # Analyze curve type
                            adaptor = BRepAdaptor_Curve(edge)
                            curve_type = adaptor.GetType()
                            
                            if curve_type == GeomAbs_Line:
                                # Line
                                p1 = curve.Value(first)
                                p2 = curve.Value(last)
                                p1_2d = self.simple_project_to_2d([[p1.X(), p1.Y(), p1.Z()]], face_id)[0]
                                p2_2d = self.simple_project_to_2d([[p2.X(), p2.Y(), p2.Z()]], face_id)[0]
                                
                                svg_elements.append({
                                    'type': 'line',
                                    'class': class_name,
                                    'x1': p1_2d[0], 'y1': p1_2d[1],
                                    'x2': p2_2d[0], 'y2': p2_2d[1]
                                })
                                all_points.extend([p1_2d, p2_2d])
                                print(f"  Added SVG LINE: ({p1_2d[0]:.2f},{p1_2d[1]:.2f}) to ({p2_2d[0]:.2f},{p2_2d[1]:.2f}) - class: {class_name}")
                                
                            elif curve_type == GeomAbs_Circle:
                                # Circle/Arc
                                circle = adaptor.Circle()
                                center = circle.Location()
                                radius = circle.Radius()
                                center_2d = self.simple_project_to_2d([[center.X(), center.Y(), center.Z()]], face_id)[0]
                                
                                # Check if it's a full circle or arc
                                param_range = abs(last - first)
                                is_full_circle = abs(param_range - 2 * math.pi) < 0.01
                                
                                if is_full_circle:
                                    svg_elements.append({
                                        'type': 'circle',
                                        'class': class_name,
                                        'cx': center_2d[0], 'cy': center_2d[1],
                                        'r': radius
                                    })
                                    # Add circle bounds to points
                                    all_points.extend([
                                        [center_2d[0] - radius, center_2d[1] - radius],
                                        [center_2d[0] + radius, center_2d[1] + radius]
                                    ])
                                    print(f"  Added SVG CIRCLE: center=({center_2d[0]:.2f},{center_2d[1]:.2f}), radius={radius:.2f} - class: {class_name}")
                                else:
                                    # Arc - use same logic as DXF for correct direction
                                    start_point = curve.Value(first)
                                    end_point = curve.Value(last)
                                    start_2d = self.simple_project_to_2d([[start_point.X(), start_point.Y(), start_point.Z()]], face_id)[0]
                                    end_2d = self.simple_project_to_2d([[end_point.X(), end_point.Y(), end_point.Z()]], face_id)[0]
                                    
                                    # Calculate angles relative to center in 2D space
                                    start_angle_rad = math.atan2(start_2d[1] - center_2d[1], start_2d[0] - center_2d[0])
                                    end_angle_rad = math.atan2(end_2d[1] - center_2d[1], end_2d[0] - center_2d[0])
                                    
                                    # Convert to degrees
                                    start_angle_deg = math.degrees(start_angle_rad) % 360
                                    end_angle_deg = math.degrees(end_angle_rad) % 360
                                    
                                    # Sample middle point to determine actual arc direction
                                    mid_param = (first + last) / 2
                                    mid_point = curve.Value(mid_param)
                                    mid_2d = self.simple_project_to_2d([[mid_point.X(), mid_point.Y(), mid_point.Z()]], face_id)[0]
                                    mid_angle_rad = math.atan2(mid_2d[1] - center_2d[1], mid_2d[0] - center_2d[0])
                                    mid_angle_deg = math.degrees(mid_angle_rad) % 360
                                    
                                    # Check if middle point is between start and end in CCW direction
                                    def is_angle_between_ccw(start, end, mid):
                                        """Check if mid is between start and end in counter-clockwise direction"""
                                        start, end, mid = start % 360, end % 360, mid % 360
                                        if start <= end:
                                            return start <= mid <= end
                                        else:
                                            return mid >= start or mid <= end
                                    
                                    is_ccw = is_angle_between_ccw(start_angle_deg, end_angle_deg, mid_angle_deg)
                                    
                                    # Calculate angle difference to determine if it's a large arc
                                    if is_ccw:
                                        angle_diff = (end_angle_deg - start_angle_deg) % 360
                                    else:
                                        angle_diff = (start_angle_deg - end_angle_deg) % 360
                                    
                                    # For SVG: large-arc-flag = 1 if angle > 180°, sweep-flag = 1 for CCW
                                    large_arc = 1 if angle_diff > 180 else 0
                                    sweep_flag = 1 if is_ccw else 0
                                    
                                    svg_elements.append({
                                        'type': 'arc',
                                        'class': class_name,
                                        'start_x': start_2d[0], 'start_y': start_2d[1],
                                        'end_x': end_2d[0], 'end_y': end_2d[1],
                                        'radius': radius,
                                        'large_arc': large_arc,
                                        'sweep_flag': sweep_flag
                                    })
                                    all_points.extend([start_2d, end_2d])
                                    print(f"  Added SVG ARC: start=({start_2d[0]:.2f},{start_2d[1]:.2f}) end=({end_2d[0]:.2f},{end_2d[1]:.2f}) radius={radius:.2f} angle_diff={angle_diff:.1f}° ccw={is_ccw} large={large_arc} sweep={sweep_flag} - class: {class_name}")
                            
                            else:
                                # Other curve types - discretize
                                points = []
                                num_points = 20
                                for i in range(num_points + 1):
                                    param = first + (last - first) * i / num_points
                                    point = curve.Value(param)
                                    point_2d = self.simple_project_to_2d([[point.X(), point.Y(), point.Z()]], face_id)[0]
                                    points.append(point_2d)
                                
                                if len(points) > 1:
                                    svg_elements.append({
                                        'type': 'polyline',
                                        'class': class_name,
                                        'points': points
                                    })
                                    all_points.extend(points)
                    
                    except Exception as e:
                        print(f"Error processing edge: {e}")
                    
                    edge_explorer.Next()
            
            # Calculate bounding box
            if not all_points:
                raise Exception("No geometry found for SVG")
            
            min_x = min(p[0] for p in all_points)
            max_x = max(p[0] for p in all_points)
            min_y = min(p[1] for p in all_points)
            max_y = max(p[1] for p in all_points)
            
            # Add padding
            padding = max(max_x - min_x, max_y - min_y) * 0.1
            min_x -= padding
            max_x += padding
            min_y -= padding
            max_y += padding
            
            width = max_x - min_x
            height = max_y - min_y
            
            # Create SVG content with real-world dimensions (millimeters)
            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}mm" height="{height:.3f}mm" 
     viewBox="{min_x:.3f} {min_y:.3f} {width:.3f} {height:.3f}">
  <defs>
    <style>
      .boundary {{ fill: none; stroke: #000000; stroke-width: 0.1mm; }}
      .hole {{ fill: none; stroke: #ff0000; stroke-width: 0.05mm; }}
    </style>
  </defs>
'''
            
            # Consolidate arcs that form complete circles
            svg_elements = self.consolidate_circle_arcs(svg_elements)
            
            # Add geometry elements
            for element in svg_elements:
                if element['type'] == 'line':
                    svg_content += f'  <line x1="{element["x1"]:.3f}" y1="{element["y1"]:.3f}" x2="{element["x2"]:.3f}" y2="{element["y2"]:.3f}" class="{element["class"]}"/>\n'
                
                elif element['type'] == 'circle':
                    svg_content += f'  <circle cx="{element["cx"]:.3f}" cy="{element["cy"]:.3f}" r="{element["r"]:.3f}" class="{element["class"]}"/>\n'
                
                elif element['type'] == 'arc':
                    svg_content += f'  <path d="M {element["start_x"]:.3f} {element["start_y"]:.3f} A {element["radius"]:.3f} {element["radius"]:.3f} 0 {element["large_arc"]} {element["sweep_flag"]} {element["end_x"]:.3f} {element["end_y"]:.3f}" class="{element["class"]}"/>\n'
                
                elif element['type'] == 'polyline':
                    points_str = ' '.join(f"{p[0]:.3f},{p[1]:.3f}" for p in element['points'])
                    svg_content += f'  <polyline points="{points_str}" class="{element["class"]}"/>\n'
            
            svg_content += '</svg>'
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.svg', mode='w', encoding='utf-8')
            temp_file.write(svg_content)
            temp_file.close()
            
            print(f"SVG created successfully: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            print(f"Error creating SVG from STEP edges: {e}")
            raise e
    
    def consolidate_circle_arcs(self, svg_elements):
        """Consolidate multiple arcs that form complete circles into single circle elements"""
        consolidated = []
        arcs_by_center_radius = {}
        
        # Group arcs by center and radius
        for element in svg_elements:
            if element['type'] == 'arc':
                # Calculate center from start point and radius (approximate)
                start_x, start_y = element['start_x'], element['start_y']
                end_x, end_y = element['end_x'], element['end_y']
                radius = element['radius']
                
                # Calculate center point from arc geometry
                # For now, use a simplified approach - group by radius and approximate center
                mid_x = (start_x + end_x) / 2
                mid_y = (start_y + end_y) / 2
                
                # Create a key for grouping (center coordinates rounded to avoid floating point issues)
                center_key = (round(radius, 3), element['class'])
                
                if center_key not in arcs_by_center_radius:
                    arcs_by_center_radius[center_key] = []
                arcs_by_center_radius[center_key].append(element)
            else:
                # Keep non-arc elements as-is
                consolidated.append(element)
        
        # Check each group of arcs to see if they form a complete circle
        for (radius, class_name), arcs in arcs_by_center_radius.items():
            if len(arcs) >= 2:
                # Try to find the actual center point
                centers = []
                for arc in arcs:
                    # Calculate center from start point, end point, and radius
                    start_x, start_y = arc['start_x'], arc['start_y']
                    end_x, end_y = arc['end_x'], arc['end_y']
                    
                    # Midpoint of chord
                    mid_x = (start_x + end_x) / 2
                    mid_y = (start_y + end_y) / 2
                    
                    # Distance from midpoint to start
                    chord_half = ((end_x - start_x)**2 + (end_y - start_y)**2)**0.5 / 2
                    
                    if chord_half < radius:
                        # Distance from midpoint to center
                        center_distance = (radius**2 - chord_half**2)**0.5
                        
                        # Perpendicular direction
                        if abs(end_x - start_x) > 0.001:
                            perp_x = -(end_y - start_y)
                            perp_y = (end_x - start_x)
                        else:
                            perp_x = 1
                            perp_y = 0
                        
                        # Normalize perpendicular vector
                        perp_length = (perp_x**2 + perp_y**2)**0.5
                        if perp_length > 0:
                            perp_x /= perp_length
                            perp_y /= perp_length
                        
                        # Two possible centers
                        center1_x = mid_x + perp_x * center_distance
                        center1_y = mid_y + perp_y * center_distance
                        center2_x = mid_x - perp_x * center_distance
                        center2_y = mid_y - perp_y * center_distance
                        
                        centers.append((center1_x, center1_y))
                        centers.append((center2_x, center2_y))
                
                # Find the most common center (within tolerance)
                if centers:
                    tolerance = 0.1
                    center_groups = []
                    
                    for cx, cy in centers:
                        added_to_group = False
                        for group in center_groups:
                            group_cx, group_cy = group[0]
                            if abs(cx - group_cx) < tolerance and abs(cy - group_cy) < tolerance:
                                group.append((cx, cy))
                                added_to_group = True
                                break
                        
                        if not added_to_group:
                            center_groups.append([(cx, cy)])
                    
                    # Find the largest group (most common center)
                    if center_groups:
                        largest_group = max(center_groups, key=len)
                        if len(largest_group) >= len(arcs):  # All arcs should share the same center
                            # Calculate average center
                            avg_cx = sum(cx for cx, cy in largest_group) / len(largest_group)
                            avg_cy = sum(cy for cx, cy in largest_group) / len(largest_group)
                            
                            # Check if the arcs cover the full circle (approximately)
                            total_angle = 0
                            for arc in arcs:
                                if 'large_arc' in arc and 'sweep_flag' in arc:
                                    # Estimate angle from arc properties
                                    if arc['large_arc'] == 1:
                                        total_angle += 180  # Large arc is at least 180°
                                    else:
                                        total_angle += 90   # Small arc estimation
                            
                            # If total angle suggests a complete circle, consolidate
                            if total_angle >= 300:  # Allow some tolerance
                                print(f"  Consolidating {len(arcs)} arcs into circle: center=({avg_cx:.2f},{avg_cy:.2f}), radius={radius:.2f}, class={class_name}")
                                consolidated.append({
                                    'type': 'circle',
                                    'class': class_name,
                                    'cx': avg_cx,
                                    'cy': avg_cy,
                                    'r': radius
                                })
                                continue
                
                # If consolidation failed, keep original arcs
                consolidated.extend(arcs)
            else:
                # Single arc, keep as-is
                consolidated.extend(arcs)
        
        return consolidated
    
    def create_svg_from_mesh(self, face_id):
        """Create SVG from mesh data (fallback method)"""
        print(f"Creating SVG from mesh for face {face_id}")
        
        try:
            face_data = self.face_data[face_id]
            mesh = face_data['mesh']
            vertices = mesh['vertices']
            triangles = mesh.get('triangles', [])
            
            if not vertices:
                raise Exception("No vertices found in mesh")
            
            # Project to 2D
            projected_vertices = self.project_to_face_plane(vertices, face_id)
            
            # Calculate bounding box
            min_x = min(v[0] for v in projected_vertices)
            max_x = max(v[0] for v in projected_vertices)
            min_y = min(v[1] for v in projected_vertices)
            max_y = max(v[1] for v in projected_vertices)
            
            width = max_x - min_x
            height = max_y - min_y
            
            # Add padding
            padding = max(width, height) * 0.1
            min_x -= padding
            max_x += padding
            min_y -= padding
            max_y += padding
            width = max_x - min_x
            height = max_y - min_y
            
            # Create SVG content with real-world dimensions (millimeters)
            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}mm" height="{height:.3f}mm" 
     viewBox="{min_x:.3f} {min_y:.3f} {width:.3f} {height:.3f}">
  <defs>
    <style>
      .face {{ fill: none; stroke: #000000; stroke-width: 0.1mm; }}
    </style>
  </defs>
'''
            
            # Add triangles as polygons
            for triangle in triangles:
                if len(triangle) == 3:
                    points = []
                    for vertex_idx in triangle:
                        if vertex_idx < len(projected_vertices):
                            v = projected_vertices[vertex_idx]
                            points.append(f"{v[0]:.3f},{v[1]:.3f}")
                    
                    if len(points) == 3:
                        svg_content += f'  <polygon points="{" ".join(points)}" class="face"/>\n'
            
            svg_content += '</svg>'
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.svg', mode='w', encoding='utf-8')
            temp_file.write(svg_content)
            temp_file.close()
            
            print(f"SVG created successfully from mesh: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            print(f"Error creating SVG from mesh: {e}")
            raise e
    
    def create_dxf_from_step_edges(self, face_id, doc, msp):
        """Extract actual edges from STEP face and convert to DXF"""
        print(f"Extracting STEP edges for face {face_id}")
        
        try:
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_WIRE
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_BSplineCurve
            from OCC.Core.BRepTools import BRepTools_WireExplorer
            import math
            
            face = self.faces[face_id]
            
            # Get all wires from the face
            wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            wire_count = 0
            
            while wire_explorer.More():
                wire = wire_explorer.Current()
                wire_count += 1
                print(f"Processing wire {wire_count}")
                
                # Determine layer name
                layer_name = 'BOUNDARY' if wire_count == 1 else 'HOLES'
                
                # Create layer if not exists
                if layer_name not in [layer.dxf.name for layer in doc.layers]:
                    color = 1 if layer_name == 'BOUNDARY' else 2
                    doc.layers.new(layer_name, dxfattribs={'color': color})
                
                # Process each edge in the wire
                edge_explorer = BRepTools_WireExplorer(wire)
                
                while edge_explorer.More():
                    edge = edge_explorer.Current()
                    
                    try:
                        # Get curve from edge
                        curve, first, last = BRep_Tool.Curve(edge)
                        if curve:
                            # Analyze curve type
                            adaptor = BRepAdaptor_Curve(edge)
                            curve_type = adaptor.GetType()
                            
                            if curve_type == GeomAbs_Line:
                                # Line: add as LINE entity
                                p1 = curve.Value(first)
                                p2 = curve.Value(last)
                                p1_2d = self.simple_project_to_2d([[p1.X(), p1.Y(), p1.Z()]], face_id)[0]
                                p2_2d = self.simple_project_to_2d([[p2.X(), p2.Y(), p2.Z()]], face_id)[0]
                                
                                msp.add_line(
                                    p1_2d, p2_2d,
                                    dxfattribs={'layer': layer_name}
                                )
                                print(f"  Added LINE: ({p1_2d[0]:.2f},{p1_2d[1]:.2f}) to ({p2_2d[0]:.2f},{p2_2d[1]:.2f})")
                                
                            elif curve_type == GeomAbs_Circle:
                                # Circle/Arc: add as CIRCLE or ARC entity
                                try:
                                    # Get circle properties
                                    circle = adaptor.Circle()
                                    center = circle.Location()
                                    radius = circle.Radius()
                                    
                                    # Project center to 2D
                                    center_2d = self.simple_project_to_2d([[center.X(), center.Y(), center.Z()]], face_id)[0]
                                    
                                    # Check if it's a full circle or arc
                                    param_range = abs(last - first)
                                    is_full_circle = abs(param_range - 2 * math.pi) < 0.01
                                    
                                    if is_full_circle:
                                        # Add as CIRCLE
                                        msp.add_circle(
                                            center_2d, radius,
                                            dxfattribs={'layer': layer_name}
                                        )
                                        print(f"  Added CIRCLE: center=({center_2d[0]:.2f},{center_2d[1]:.2f}), radius={radius:.2f}")
                                    else:
                                        # Add as ARC - proper angle calculation
                                        # Get start and end points
                                        start_point = curve.Value(first)
                                        end_point = curve.Value(last)
                                        
                                        # Project start and end points to 2D
                                        start_2d = self.simple_project_to_2d([[start_point.X(), start_point.Y(), start_point.Z()]], face_id)[0]
                                        end_2d = self.simple_project_to_2d([[end_point.X(), end_point.Y(), end_point.Z()]], face_id)[0]
                                        
                                        # Calculate angles relative to center in 2D space
                                        start_angle_rad = math.atan2(start_2d[1] - center_2d[1], start_2d[0] - center_2d[0])
                                        end_angle_rad = math.atan2(end_2d[1] - center_2d[1], end_2d[0] - center_2d[0])
                                        
                                        # Convert to degrees
                                        start_angle_deg = math.degrees(start_angle_rad) % 360
                                        end_angle_deg = math.degrees(end_angle_rad) % 360
                                        
                                        # 実際の円弧の向きを確認するために中間点をサンプリング
                                        mid_param = (first + last) / 2
                                        mid_point = curve.Value(mid_param)
                                        mid_2d = self.simple_project_to_2d([[mid_point.X(), mid_point.Y(), mid_point.Z()]], face_id)[0]
                                        mid_angle_rad = math.atan2(mid_2d[1] - center_2d[1], mid_2d[0] - center_2d[0])
                                        mid_angle_deg = math.degrees(mid_angle_rad) % 360
                                        
                                        # 中間点が開始角度と終了角度の間にあるかをチェック
                                        def is_angle_between_ccw(start, end, mid):
                                            """反時計回りで mid が start と end の間にあるかチェック"""
                                            # 全て0-360の範囲に正規化
                                            start, end, mid = start % 360, end % 360, mid % 360
                                            
                                            if start <= end:
                                                # 通常の場合: start < mid < end
                                                return start <= mid <= end
                                            else:
                                                # 0度をまたぐ場合: mid >= start or mid <= end
                                                return mid >= start or mid <= end
                                        
                                        # 中間点が start から end への反時計回りの経路上にあるかチェック
                                        is_ccw = is_angle_between_ccw(start_angle_deg, end_angle_deg, mid_angle_deg)
                                        
                                        if not is_ccw:
                                            # 時計回りの場合、角度を入れ替える
                                            start_angle_deg, end_angle_deg = end_angle_deg, start_angle_deg

                                        msp.add_arc(
                                            center_2d, radius,
                                            start_angle_deg, end_angle_deg,
                                            dxfattribs={'layer': layer_name}
                                        )
                                        print(f"  Added ARC: center=({center_2d[0]:.2f},{center_2d[1]:.2f}), radius={radius:.2f}, angles={start_angle_deg:.1f}°-{end_angle_deg:.1f}°")
                                
                                except Exception as circle_error:
                                    print(f"  Error processing circle/arc: {circle_error}")
                                    # Fallback to polyline
                                    self.add_curve_as_polyline(edge, curve, first, last, msp, layer_name, face_id)
                                
                            elif curve_type == GeomAbs_Ellipse:
                                # Ellipse: add as ELLIPSE entity
                                try:
                                    ellipse = adaptor.Ellipse()
                                    center = ellipse.Location()
                                    major_radius = ellipse.MajorRadius()
                                    minor_radius = ellipse.MinorRadius()
                                    
                                    # Project center to 2D
                                    center_2d = self.simple_project_to_2d([[center.X(), center.Y(), center.Z()]], face_id)[0]
                                    
                                    # Get major axis direction
                                    major_axis = ellipse.XAxis().Direction()
                                    major_axis_2d = self.simple_project_to_2d([[major_axis.X(), major_axis.Y(), major_axis.Z()]], face_id)[0]
                                    
                                    # Calculate ratio
                                    ratio = minor_radius / major_radius
                                    
                                    # Check if it's a full ellipse or arc
                                    param_range = abs(last - first)
                                    is_full_ellipse = abs(param_range - 2 * math.pi) < 0.01
                                    
                                    if is_full_ellipse:
                                        msp.add_ellipse(
                                            center_2d,
                                            major_axis_2d,
                                            ratio,
                                            dxfattribs={'layer': layer_name}
                                        )
                                        print(f"  Added ELLIPSE: center=({center_2d[0]:.2f},{center_2d[1]:.2f}), major={major_radius:.2f}, minor={minor_radius:.2f}")
                                    else:
                                        # Elliptical arc - use polyline approximation
                                        self.add_curve_as_polyline(edge, curve, first, last, msp, layer_name, face_id)
                                
                                except Exception as ellipse_error:
                                    print(f"  Error processing ellipse: {ellipse_error}")
                                    # Fallback to polyline
                                    self.add_curve_as_polyline(edge, curve, first, last, msp, layer_name, face_id)
                                
                            else:
                                # Other curves (B-splines, etc.): use polyline approximation
                                self.add_curve_as_polyline(edge, curve, first, last, msp, layer_name)
                    
                    except Exception as edge_error:
                        print(f"  Error processing edge: {edge_error}")
                    
                    edge_explorer.Next()
                
                wire_explorer.Next()
            
            # Save file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
            try:
                doc.saveas(temp_file.name)
                temp_file.close()
                print(f"STEP-based DXF saved to: {temp_file.name}")
                return temp_file.name, wire_count
            except Exception as save_error:
                temp_file.close()
                raise Exception(f"Failed to save STEP-based DXF: {str(save_error)}")
                
        except Exception as e:
            print(f"STEP edge extraction error: {e}")
            raise e
    
    def add_curve_as_polyline(self, edge, curve, first, last, msp, layer_name, face_id):
        """Add a curve as polyline approximation for complex curves"""
        try:
            # Sample points along the curve
            num_points = 12  # Good balance between accuracy and file size
            points_3d = []
            
            for i in range(num_points + 1):
                param = first + (last - first) * i / num_points
                point = curve.Value(param)
                points_3d.append([point.X(), point.Y(), point.Z()])
            
            # Project to 2D
            points_2d = self.simple_project_to_2d(points_3d, face_id)
            
            if len(points_2d) >= 2:
                # Remove consecutive duplicates
                clean_points = [points_2d[0]]
                for i in range(1, len(points_2d)):
                    prev = clean_points[-1]
                    curr = points_2d[i]
                    dist = ((curr[0] - prev[0])**2 + (curr[1] - prev[1])**2)**0.5
                    if dist > 0.001:  # Very small threshold
                        clean_points.append(curr)
                
                if len(clean_points) >= 2:
                    # Add as polyline
                    msp.add_lwpolyline(
                        clean_points,
                        close=False,
                        dxfattribs={'layer': layer_name}
                    )
                    print(f"  Added POLYLINE approximation with {len(clean_points)} points")
        
        except Exception as e:
            print(f"  Error adding curve as polyline: {e}")
    
    def create_dxf_from_mesh_improved(self, face_id, doc, msp):
        """Improved mesh-based DXF creation with better edge detection"""
        print(f"Creating improved mesh-based DXF for face {face_id}")
        
        # Get face data
        face_data = self.face_data[face_id]
        mesh = face_data['mesh']
        vertices = mesh['vertices']
        
        if not vertices or len(vertices) < 3:
            # Create simple test shape
            msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
            doc.saveas(temp_file.name)
            temp_file.close()
            return temp_file.name, 1
        
        # Project vertices to 2D plane
        points_2d = self.simple_project_to_2d(vertices, face_id)
        
        if not points_2d or len(points_2d) < 3:
            # Fallback
            msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
            doc.saveas(temp_file.name)
            temp_file.close()
            return temp_file.name, 1
        
        # Use triangles to find actual edges
        boundary_edges = []
        triangles = mesh.get('triangles', [])
        
        if triangles:
            # Find boundary edges (edges that appear in only one triangle)
            edge_count = {}
            for triangle in triangles:
                edges = [
                    (min(triangle[0], triangle[1]), max(triangle[0], triangle[1])),
                    (min(triangle[1], triangle[2]), max(triangle[1], triangle[2])),
                    (min(triangle[2], triangle[0]), max(triangle[2], triangle[0]))
                ]
                for edge in edges:
                    edge_count[edge] = edge_count.get(edge, 0) + 1
            
            # Get boundary edges (appear only once)
            for edge, count in edge_count.items():
                if count == 1:
                    boundary_edges.append(edge)
            
            print(f"Found {len(boundary_edges)} boundary edges from {len(triangles)} triangles")
        
        if boundary_edges:
            # Convert boundary edges to connected path
            boundary_path = self.edges_to_path(boundary_edges, points_2d)
            if boundary_path and len(boundary_path) >= 3:
                msp.add_lwpolyline(boundary_path, close=True)
                print(f"Added boundary path with {len(boundary_path)} points")
        else:
            # Fallback to convex hull
            boundary = self.extract_boundary(points_2d)
            if boundary and len(boundary) >= 3:
                msp.add_lwpolyline(boundary, close=True)
                print(f"Added fallback boundary with {len(boundary)} points")
        
        # Save file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
        try:
            doc.saveas(temp_file.name)
            temp_file.close()
            print(f"Mesh-based DXF saved to: {temp_file.name}")
            return temp_file.name, 1
        except Exception as e:
            temp_file.close()
            raise Exception(f"Failed to save mesh-based DXF: {str(e)}")
    
    def edges_to_path(self, edges, vertices):
        """Convert edge list to connected path"""
        if not edges:
            return []
        
        # Build adjacency map
        adjacency = {}
        for v1, v2 in edges:
            if v1 not in adjacency:
                adjacency[v1] = []
            if v2 not in adjacency:
                adjacency[v2] = []
            adjacency[v1].append(v2)
            adjacency[v2].append(v1)
        
        # Find a starting vertex (preferably with degree 2)
        start_vertex = None
        for vertex, neighbors in adjacency.items():
            if len(neighbors) <= 2:
                start_vertex = vertex
                break
        
        if start_vertex is None:
            start_vertex = list(adjacency.keys())[0]
        
        # Trace the path
        path = [start_vertex]
        current = start_vertex
        previous = None
        
        while True:
            neighbors = [n for n in adjacency[current] if n != previous]
            if not neighbors:
                break
            
            next_vertex = neighbors[0]
            if next_vertex == start_vertex and len(path) > 2:
                break  # Completed the loop
            
            path.append(next_vertex)
            previous = current
            current = next_vertex
            
            if len(path) > len(edges) + 1:  # Prevent infinite loops
                break
        
        # Convert vertex indices to 2D coordinates
        path_2d = []
        for vertex_idx in path:
            if vertex_idx < len(vertices):
                path_2d.append(vertices[vertex_idx])
        
        return path_2d
    
    def get_face_normal(self, face_id):
        """面の法線ベクトルを計算"""
        try:
            if HAS_PYTHONOCC and hasattr(self, 'step_shape') and self.step_shape and face_id < len(self.faces):
                from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
                from OCC.Core.GProp import GProp_GProps
                from OCC.Core.BRepLProp import BRepLProp_SLProps
                from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
                
                face = self.faces[face_id]
                
                # 面の中心点を取得
                props = GProp_GProps()
                brepgprop_SurfaceProperties(face, props)
                center = props.CentreOfMass()
                
                # 面のアダプター作成
                surface = BRepAdaptor_Surface(face)
                
                # UV パラメータの中間値を取得
                u_min, u_max, v_min, v_max = surface.FirstUParameter(), surface.LastUParameter(), surface.FirstVParameter(), surface.LastVParameter()
                u_mid = (u_min + u_max) / 2
                v_mid = (v_min + v_max) / 2
                
                # 法線ベクトルを計算
                props = BRepLProp_SLProps(surface, u_mid, v_mid, 1, 1e-6)
                if props.IsNormalDefined():
                    normal = props.Normal()
                    return [normal.X(), normal.Y(), normal.Z()]
            
            # フォールバック: メッシュから法線を計算
            return self.calculate_mesh_normal(face_id)
            
        except Exception as e:
            print(f"Error calculating face normal: {e}")
            return self.calculate_mesh_normal(face_id)
    
    def calculate_mesh_normal(self, face_id):
        """メッシュから法線ベクトルを計算"""
        try:
            face_data = self.face_data[face_id]
            mesh = face_data['mesh']
            vertices = mesh['vertices']
            triangles = mesh.get('triangles', [])
            
            if len(vertices) < 3 or not triangles:
                return [0, 0, 1]  # デフォルト: Z軸方向
            
            # 最初の三角形から法線を計算
            triangle = triangles[0]
            if len(triangle) >= 3:
                v1 = vertices[triangle[0]]
                v2 = vertices[triangle[1]]
                v3 = vertices[triangle[2]]
                
                # 外積で法線ベクトルを計算
                edge1 = [v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]]
                edge2 = [v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]]
                
                normal = [
                    edge1[1] * edge2[2] - edge1[2] * edge2[1],
                    edge1[2] * edge2[0] - edge1[0] * edge2[2],
                    edge1[0] * edge2[1] - edge1[1] * edge2[0]
                ]
                
                # 正規化
                length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
                if length > 0:
                    normal = [normal[0]/length, normal[1]/length, normal[2]/length]
                
                return normal
            
            return [0, 0, 1]  # デフォルト
            
        except Exception as e:
            print(f"Error calculating mesh normal: {e}")
            return [0, 0, 1]
    
    def project_to_face_plane(self, vertices, face_id):
        """面の法線ベクトルを基準にした適切な2D投影"""
        if not vertices:
            return []
        
        # 面の法線ベクトルを取得
        normal = self.get_face_normal(face_id)
        print(f"Face {face_id} normal: [{normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f}]")
        
        # 法線ベクトルを正規化
        length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
        if length > 0:
            normal = [normal[0]/length, normal[1]/length, normal[2]/length]
        
        # 法線ベクトルに基づいて適切な投影軸を決定
        abs_normal = [abs(normal[0]), abs(normal[1]), abs(normal[2])]
        max_component = max(abs_normal)
        
        if abs_normal[2] == max_component:
            # Z成分が最大 -> XY平面への投影
            u_axis = [1, 0, 0]
            v_axis = [0, 1, 0]
            print("Projecting to XY plane")
        elif abs_normal[1] == max_component:
            # Y成分が最大 -> XZ平面への投影
            u_axis = [1, 0, 0]
            v_axis = [0, 0, 1]
            print("Projecting to XZ plane")
        else:
            # X成分が最大 -> YZ平面への投影
            u_axis = [0, 1, 0]
            v_axis = [0, 0, 1]
            print("Projecting to YZ plane")
        
        # より正確な投影のため、法線に垂直な2つのベクトルを計算
        # Gram-Schmidt 直交化プロセスを使用
        def normalize_vector(v):
            length = (v[0]**2 + v[1]**2 + v[2]**2)**0.5
            return [v[0]/length, v[1]/length, v[2]/length] if length > 0 else v
        
        def dot_product(a, b):
            return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
        
        def subtract_vectors(a, b):
            return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]
        
        def scale_vector(v, s):
            return [v[0]*s, v[1]*s, v[2]*s]
        
        # 法線に垂直な第一軸を計算
        dot_nu = dot_product(normal, u_axis)
        u_proj = subtract_vectors(u_axis, scale_vector(normal, dot_nu))
        u_proj = normalize_vector(u_proj)
        
        # 法線と第一軸に垂直な第二軸を計算
        dot_nv = dot_product(normal, v_axis)
        dot_uv = dot_product(u_proj, v_axis)
        v_proj = subtract_vectors(v_axis, scale_vector(normal, dot_nv))
        v_proj = subtract_vectors(v_proj, scale_vector(u_proj, dot_uv))
        v_proj = normalize_vector(v_proj)
        
        # 各頂点を2D平面に投影
        points_2d = []
        for vertex in vertices:
            u_coord = dot_product(vertex, u_proj)
            v_coord = dot_product(vertex, v_proj)
            points_2d.append((u_coord, v_coord))
        
        print(f"Projected {len(vertices)} vertices to 2D")
        return points_2d
    
    def simple_project_to_2d(self, vertices, face_id=None):
        """面IDが指定されている場合は適切な投影、そうでなければ従来の方法"""
        if face_id is not None:
            return self.project_to_face_plane(vertices, face_id)
        
        # 従来の簡易投影（後方互換性のため）
        if not vertices:
            return []
        
        # Find the plane with least variation
        x_coords = [v[0] for v in vertices]
        y_coords = [v[1] for v in vertices]
        z_coords = [v[2] for v in vertices]
        
        x_var = max(x_coords) - min(x_coords) if x_coords else 0
        y_var = max(y_coords) - min(y_coords) if y_coords else 0
        z_var = max(z_coords) - min(z_coords) if z_coords else 0
        
        print(f"Variations: X={x_var:.2f}, Y={y_var:.2f}, Z={z_var:.2f}")
        
        # Project to plane with least variation (flattest)
        if z_var <= x_var and z_var <= y_var:
            # Z is most constant, use X-Y plane
            return [(v[0], v[1]) for v in vertices]
        elif y_var <= x_var:
            # Y is most constant, use X-Z plane  
            return [(v[0], v[2]) for v in vertices]
        else:
            # X is most constant, use Y-Z plane
            return [(v[1], v[2]) for v in vertices]
    
    def extract_boundary(self, points_2d):
        """Extract outer boundary from 2D points"""
        if len(points_2d) < 3:
            return points_2d
        
        # Remove duplicates
        unique_points = []
        for p in points_2d:
            is_duplicate = False
            for existing in unique_points:
                if abs(p[0] - existing[0]) < 0.001 and abs(p[1] - existing[1]) < 0.001:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_points.append(p)
        
        if len(unique_points) < 3:
            return points_2d
        
        # Use convex hull for boundary
        return self.convex_hull(unique_points)
    
    def convex_hull(self, points):
        """Simple convex hull algorithm"""
        if len(points) < 3:
            return points
        
        # Sort points by x coordinate
        points = sorted(set(points))
        if len(points) < 3:
            return points
        
        # Build lower hull
        lower = []
        for p in points:
            while len(lower) >= 2 and self.cross_product(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        
        # Build upper hull
        upper = []
        for p in reversed(points):
            while len(upper) >= 2 and self.cross_product(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        
        return lower[:-1] + upper[:-1]
    
    def cross_product(self, o, a, b):
        """Calculate cross product for convex hull"""
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    
    def find_holes(self, all_points, boundary):
        """Find holes inside the boundary"""
        if len(all_points) < 10:
            return []
        
        holes = []
        
        # Find points inside boundary that might form holes
        inside_points = []
        for point in all_points:
            if self.point_in_polygon(point, boundary):
                inside_points.append(point)
        
        if len(inside_points) < 6:
            return []
        
        # Group points into potential circular holes
        holes = self.detect_circular_clusters(inside_points)
        
        return holes
    
    def point_in_polygon(self, point, polygon):
        """Check if point is inside polygon using ray casting"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def detect_circular_clusters(self, points):
        """Detect circular clusters in points"""
        if len(points) < 6:
            return []
        
        holes = []
        used_points = set()
        
        for i, center_candidate in enumerate(points):
            if i in used_points:
                continue
            
            cx, cy = center_candidate
            
            # Find points at similar distance from this center
            distances = []
            point_distances = []
            
            for j, (px, py) in enumerate(points):
                if j in used_points:
                    continue
                dist = ((px - cx)**2 + (py - cy)**2)**0.5
                if 1.0 <= dist <= 10.0:  # Reasonable hole size
                    distances.append(dist)
                    point_distances.append((j, px, py, dist))
            
            if len(distances) < 6:
                continue
            
            # Find most common distance (potential radius)
            distances.sort()
            for d in distances:
                tolerance = d * 0.2
                similar_points = []
                
                for j, px, py, dist in point_distances:
                    if abs(dist - d) <= tolerance:
                        similar_points.append((px, py))
                
                if len(similar_points) >= 6:  # Reduce requirement for hole detection
                    # Mark points as used
                    for j, px, py, dist in point_distances:
                        if abs(dist - d) <= tolerance:
                            used_points.add(j)
                    
                    holes.append(similar_points)
                    print(f"Found potential hole with {len(similar_points)} points at distance {d:.2f}")
                    break
        
        return holes
    
    def is_circle(self, points):
        """Check if points form a circle"""
        if len(points) < 6:
            return False
        
        # Calculate center and check if all points are equidistant
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        
        distances = [((p[0] - cx)**2 + (p[1] - cy)**2)**0.5 for p in points]
        avg_dist = sum(distances) / len(distances)
        
        # Check if all distances are similar (more lenient for hole detection)
        tolerance = avg_dist * 0.25  # 25% tolerance for better detection
        similar_count = 0
        for dist in distances:
            if abs(dist - avg_dist) <= tolerance:
                similar_count += 1
        
        # If most points are at similar distance, consider it a circle
        return similar_count >= len(points) * 0.75  # 75% of points must be similar
    
    def get_circle_center_radius(self, points):
        """Get center and radius of circular points"""
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        
        distances = [((p[0] - cx)**2 + (p[1] - cy)**2)**0.5 for p in points]
        radius = sum(distances) / len(distances)
        
        return (cx, cy), radius
    
    def get_dxf_preview_data(self, face_id):
        """Get DXF geometry data for preview (JSON format)"""
        if face_id >= len(self.face_data):
            raise Exception("Invalid face ID")
        
        print(f"Generating DXF preview data for face {face_id}")
        
        # Get face data
        face_data = self.face_data[face_id]
        mesh = face_data['mesh']
        vertices = mesh['vertices']
        
        preview_data = {
            'face_id': face_id,
            'face_type': face_data.get('type', 'Unknown'),
            'boundary': [],
            'holes': [],
            'dimensions': {},
            'entity_count': 0
        }
        
        if not vertices or len(vertices) < 3:
            # Return minimal preview for empty face
            preview_data['boundary'] = {
                'type': 'LWPOLYLINE',
                'points': [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                'closed': True
            }
            preview_data['entity_count'] = 1
            preview_data['dimensions'] = {
                'width': 10.0,
                'height': 10.0,
                'bounds': {'x_min': 0, 'x_max': 10, 'y_min': 0, 'y_max': 10}
            }
            return preview_data
        
        # Project vertices to 2D
        points_2d = self.simple_project_to_2d(vertices, face_id)
        
        if not points_2d or len(points_2d) < 3:
            # Fallback preview
            preview_data['boundary'] = {
                'type': 'LWPOLYLINE',
                'points': [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                'closed': True
            }
            preview_data['entity_count'] = 1
            preview_data['dimensions'] = {
                'width': 10.0,
                'height': 10.0,
                'bounds': {'x_min': 0, 'x_max': 10, 'y_min': 0, 'y_max': 10}
            }
            return preview_data
        
        # Get boundary using the same logic as DXF creation
        boundary = self.get_preview_boundary(face_data, points_2d)
        
        if boundary and len(boundary) >= 3:
            # Calculate dimensions
            x_coords = [p[0] for p in boundary]
            y_coords = [p[1] for p in boundary]
            
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            width = max(x_max - x_min, 0.1)  # Ensure minimum width
            height = max(y_max - y_min, 0.1)  # Ensure minimum height
            
            preview_data['dimensions'] = {
                'width': round(width, 3),
                'height': round(height, 3),
                'bounds': {
                    'x_min': round(x_min, 3), 'x_max': round(x_max, 3),
                    'y_min': round(y_min, 3), 'y_max': round(y_max, 3)
                }
            }
            
            # Add boundary to preview
            boundary_points = []
            for p in boundary:
                if len(p) >= 2:  # Ensure point has at least x,y coordinates
                    boundary_points.append([round(float(p[0]), 3), round(float(p[1]), 3)])
            
            # Ensure we have valid points
            if len(boundary_points) >= 3:
                # Close the boundary if not already closed
                if boundary_points[0] != boundary_points[-1]:
                    boundary_points.append(boundary_points[0])
                
                preview_data['boundary'] = {
                    'type': 'LWPOLYLINE',
                    'points': boundary_points,
                    'closed': True
                }
                preview_data['entity_count'] += 1
            else:
                # Fallback to default square
                preview_data['boundary'] = {
                    'type': 'LWPOLYLINE',
                    'points': [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                    'closed': True
                }
                preview_data['entity_count'] += 1
                preview_data['dimensions'] = {
                    'width': 10.0,
                    'height': 10.0,
                    'bounds': {'x_min': 0, 'x_max': 10, 'y_min': 0, 'y_max': 10}
                }
        else:
            # No valid boundary found, use default
            preview_data['boundary'] = {
                'type': 'LWPOLYLINE',
                'points': [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                'closed': True
            }
            preview_data['entity_count'] += 1
            preview_data['dimensions'] = {
                'width': 10.0,
                'height': 10.0,
                'bounds': {'x_min': 0, 'x_max': 10, 'y_min': 0, 'y_max': 10}
            }
        
        # Detect holes (only if we have a valid boundary)
        if boundary and len(boundary) >= 3:
            try:
                holes = self.find_holes(points_2d, boundary)
                for hole in holes:
                    if len(hole) >= 3:
                        if self.is_circle(hole):
                            # Add circle hole
                            center, radius = self.get_circle_center_radius(hole)
                            preview_data['holes'].append({
                                'type': 'CIRCLE',
                                'center': [round(float(center[0]), 3), round(float(center[1]), 3)],
                                'radius': round(float(radius), 3)
                            })
                            preview_data['entity_count'] += 1
                        else:
                            # Add polyline hole
                            hole_points = []
                            for p in hole:
                                if len(p) >= 2:
                                    hole_points.append([round(float(p[0]), 3), round(float(p[1]), 3)])
                            
                            if len(hole_points) >= 3:
                                if hole_points[0] != hole_points[-1]:
                                    hole_points.append(hole_points[0])  # Close the hole
                                
                                preview_data['holes'].append({
                                    'type': 'LWPOLYLINE',
                                    'points': hole_points,
                                    'closed': True
                                })
                                preview_data['entity_count'] += 1
            except Exception as e:
                print(f"Error detecting holes: {e}")
                # Continue without holes
        
        print(f"Preview data: {preview_data['entity_count']} entities, {len(preview_data['holes'])} holes")
        return preview_data
    
    def get_preview_boundary(self, face_data, points_2d):
        """Get boundary for preview using same logic as DXF creation"""
        mesh = face_data['mesh']
        triangles = mesh.get('triangles', [])
        
        if triangles and len(points_2d) > 3:
            # Use edge-based boundary detection
            boundary_edges = []
            edge_count = {}
            
            for triangle in triangles:
                edges = [
                    (min(triangle[0], triangle[1]), max(triangle[0], triangle[1])),
                    (min(triangle[1], triangle[2]), max(triangle[1], triangle[2])),
                    (min(triangle[2], triangle[0]), max(triangle[2], triangle[0]))
                ]
                for edge in edges:
                    edge_count[edge] = edge_count.get(edge, 0) + 1
            
            # Get boundary edges (appear only once)
            for edge, count in edge_count.items():
                if count == 1:
                    boundary_edges.append(edge)
            
            if boundary_edges:
                boundary_path = self.edges_to_path(boundary_edges, points_2d)
                if boundary_path and len(boundary_path) >= 3:
                    return boundary_path
        
        # Fallback to convex hull
        return self.extract_boundary(points_2d)
    
    
    def extract_face_geometry(self, face):
        """Extract boundary and holes from face using pythonocc"""
        try:
            from OCC.Core.BRepTools import BRepTools_WireExplorer
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_WIRE
            
            print("Starting face geometry extraction...")
            
            # Check if face is valid
            if not face:
                raise Exception("Face is None")
            
            # Get outer wire
            print("Getting outer wire...")
            outer_wire = BRep_Tool.OuterWire(face)
            if not outer_wire:
                raise Exception("Could not get outer wire")
                
            print("Extracting boundary points...")
            boundary_points = self.extract_wire_points(outer_wire)
            print(f"Got {len(boundary_points)} boundary points")
            
            # Get holes (inner wires)
            holes = []
            print("Looking for holes...")
            wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            wire_count = 0
            while wire_explorer.More():
                wire = wire_explorer.Current()
                wire_count += 1
                print(f"Processing wire {wire_count}")
                
                if not wire.IsSame(outer_wire):
                    print(f"Found hole wire {wire_count}")
                    hole_points = self.extract_wire_points(wire)
                    if hole_points:
                        holes.append(hole_points)
                        print(f"Added hole with {len(hole_points)} points")
                wire_explorer.Next()
            
            print(f"Final result: {len(boundary_points)} boundary points, {len(holes)} holes")
            return boundary_points, holes
            
        except Exception as e:
            import traceback
            print(f"Error extracting face geometry: {e}")
            traceback.print_exc()
            return [], []
    
    def extract_wire_points(self, wire):
        """Extract points from a wire with enhanced geometric analysis"""
        try:
            from OCC.Core.BRepTools import BRepTools_WireExplorer
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            
            points = []
            wire_explorer = BRepTools_WireExplorer(wire)
            
            while wire_explorer.More():
                edge = wire_explorer.Current()
                try:
                    # Analyze edge type for better geometry extraction
                    adaptor = BRepAdaptor_Curve(edge)
                    curve_type = adaptor.GetType()
                    
                    curve, first, last = BRep_Tool.Curve(edge)
                    if curve:
                        if curve_type == GeomAbs_Line:
                            # For lines, take start and end points
                            start_point = curve.Value(first)
                            end_point = curve.Value(last)
                            points.append([start_point.X(), start_point.Y(), start_point.Z()])
                            points.append([end_point.X(), end_point.Y(), end_point.Z()])
                        elif curve_type == GeomAbs_Circle:
                            # For circles/arcs, take sufficient points for smooth curves
                            num_samples = 16  # Increased for better circle approximation
                            for i in range(num_samples):
                                param = first + (last - first) * i / num_samples
                                point = curve.Value(param)
                                points.append([point.X(), point.Y(), point.Z()])
                        elif curve_type == GeomAbs_Ellipse:
                            # For ellipses, take more points for accurate representation
                            num_samples = 12
                            for i in range(num_samples):
                                param = first + (last - first) * i / num_samples
                                point = curve.Value(param)
                                points.append([point.X(), point.Y(), point.Z()])
                        else:
                            # For other curves (splines, etc.), dense sampling
                            num_samples = 10
                            for i in range(num_samples):
                                param = first + (last - first) * i / (num_samples - 1) if num_samples > 1 else first
                                point = curve.Value(param)
                                points.append([point.X(), point.Y(), point.Z()])
                except Exception as edge_error:
                    print(f"Error processing edge: {edge_error}")
                    pass
                wire_explorer.Next()
            
            # Remove duplicate points
            unique_points = []
            for point in points:
                is_duplicate = False
                for existing in unique_points:
                    if (abs(point[0] - existing[0]) < 0.001 and 
                        abs(point[1] - existing[1]) < 0.001 and 
                        abs(point[2] - existing[2]) < 0.001):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique_points.append(point)
            
            print(f"Extracted {len(unique_points)} unique points from wire")
            return unique_points
            
        except Exception as e:
            print(f"Error extracting wire points: {e}")
            return []
    
    
    
    
    def create_test_dxf(self):
        """Create a simple test DXF file to verify the workflow"""
        doc = ezdxf.new('R2010')
        doc.units = ezdxf.units.MM
        msp = doc.modelspace()
        
        # Create basic layers
        doc.layers.new('GEOMETRY', dxfattribs={'color': 1})
        doc.layers.new('TEXT', dxfattribs={'color': 3})
        doc.layers.new('CONSTRUCTION', dxfattribs={'color': 8})
        
        # Add simple, guaranteed visible geometry
        # Square at origin
        square = [(-25, -25), (25, -25), (25, 25), (-25, 25), (-25, -25)]
        msp.add_lwpolyline(square, close=True, dxfattribs={'layer': 'GEOMETRY', 'color': 1})
        
        # Circle
        msp.add_circle((0, 0), 15, dxfattribs={'layer': 'GEOMETRY', 'color': 1})
        
        # Construction lines
        msp.add_line((-50, 0), (50, 0), dxfattribs={'layer': 'CONSTRUCTION', 'color': 8})
        msp.add_line((0, -50), (0, 50), dxfattribs={'layer': 'CONSTRUCTION', 'color': 8})
        
        # Text
        msp.add_text(
            "TEST DXF - If you can see this, DXF export is working",
            dxfattribs={
                'height': 3.0,
                'layer': 'TEXT',
                'insert': (0, -40),
                'halign': 1,
                'valign': 1,
                'color': 3
            }
        )
        
        # Version info
        msp.add_text(
            "Generated by STEP to DXF Webapp v1.1",
            dxfattribs={
                'height': 2.0,
                'layer': 'TEXT', 
                'insert': (0, 35),
                'halign': 1,
                'valign': 1,
                'color': 3
            }
        )
        
        # Force extents
        try:
            doc.header['$EXTMIN'] = (-60, -60, 0)
            doc.header['$EXTMAX'] = (60, 60, 0)
            doc.header['$LIMMIN'] = (-60, -60)
            doc.header['$LIMMAX'] = (60, 60)
        except:
            pass
        
        # Save file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
        try:
            doc.saveas(temp_file.name)
            temp_file.close()
            return temp_file.name, 6  # 6 entities created
        except Exception as e:
            temp_file.close()
            raise Exception(f"Failed to create test DXF: {str(e)}")
    
    def create_guaranteed_dxf(self, face_id):
        """Create a guaranteed-to-work DXF with basic geometry"""
        print(f"Creating guaranteed DXF for face {face_id}")
        
        # Create DXF document
        doc = ezdxf.new('R2010')
        doc.units = ezdxf.units.MM
        msp = doc.modelspace()
        
        # Create basic layers
        doc.layers.new('OUTLINE', dxfattribs={'color': 1, 'lineweight': 50})
        doc.layers.new('TEXT', dxfattribs={'color': 3, 'lineweight': 25})
        doc.layers.new('REFERENCE', dxfattribs={'color': 8, 'lineweight': 25})
        
        # Get face info if available
        face_type = "Unknown"
        if face_id < len(self.face_data):
            face_type = self.face_data[face_id].get('type', 'Unknown')
        
        # Create guaranteed visible geometry - square outline
        square_size = 20.0
        square_points = [
            (-square_size, -square_size),
            (square_size, -square_size), 
            (square_size, square_size),
            (-square_size, square_size)
        ]
        
        # Add main outline
        msp.add_lwpolyline(
            square_points, 
            close=True, 
            dxfattribs={
                'layer': 'OUTLINE',
                'color': 1,
                'lineweight': 50
            }
        )
        print("Added main outline square")
        
        # Add inner geometry for visual interest
        inner_size = square_size * 0.6
        inner_circle = msp.add_circle(
            (0, 0), 
            inner_size, 
            dxfattribs={
                'layer': 'OUTLINE',
                'color': 1,
                'lineweight': 35
            }
        )
        print("Added inner circle")
        
        # Add reference lines
        axis_length = square_size * 1.2
        msp.add_line((-axis_length, 0), (axis_length, 0), dxfattribs={'layer': 'REFERENCE', 'color': 8})
        msp.add_line((0, -axis_length), (0, axis_length), dxfattribs={'layer': 'REFERENCE', 'color': 8})
        print("Added reference axes")
        
        # Add informational text
        text_height = 3.0
        
        main_text = f"Face {face_id + 1} - {face_type}"
        msp.add_text(
            main_text,
            dxfattribs={
                'height': text_height,
                'layer': 'TEXT',
                'insert': (0, square_size + 5),
                'halign': 1,  # Center
                'valign': 0,  # Baseline
                'color': 3
            }
        )
        
        info_text = "Guaranteed geometry - DXF export working"
        msp.add_text(
            info_text,
            dxfattribs={
                'height': text_height * 0.7,
                'layer': 'TEXT',
                'insert': (0, -square_size - 8),
                'halign': 1,
                'valign': 0,
                'color': 3
            }
        )
        
        print("Added text labels")
        
        # Set proper document extents
        extent = square_size + 15
        doc.header['$EXTMIN'] = (-extent, -extent, 0)
        doc.header['$EXTMAX'] = (extent, extent, 0)
        doc.header['$LIMMIN'] = (-extent, -extent)
        doc.header['$LIMMAX'] = (extent, extent)
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
        try:
            doc.saveas(temp_file.name)
            temp_file.close()
            print(f"Guaranteed DXF saved to {temp_file.name}")
            return temp_file.name, 5  # 5 entities guaranteed
        except Exception as save_error:
            temp_file.close()
            raise Exception(f"Failed to save guaranteed DXF: {str(save_error)}")
    
    


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        import sys
        return jsonify({
            'status': 'ok',
            'pythonocc_available': HAS_PYTHONOCC,
            'ezdxf_available': HAS_EZDXF,
            'python_version': sys.version,
            'flask_version': getattr(Flask, '__version__', 'unknown')
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'pythonocc_available': HAS_PYTHONOCC,
            'ezdxf_available': HAS_EZDXF
        }), 500

@app.route('/api/debug')
def debug_info():
    """Debug information endpoint"""
    try:
        # Test pythonocc import
        reader_test = "❌ pythonocc-core not available"
        if HAS_PYTHONOCC:
            try:
                from OCC.Core.STEPControl import STEPControl_Reader
                reader_test = "✅ STEPControl_Reader imported successfully"
            except Exception as import_error:
                reader_test = f"❌ Import error: {str(import_error)}"
        
        return jsonify({
            'pythonocc_status': reader_test,
            'pythonocc_available': HAS_PYTHONOCC,
            'ezdxf_status': "✅ Available" if HAS_EZDXF else "❌ Not available",
            'temp_dir': tempfile.gettempdir(),
            'max_content_length': app.config.get('MAX_CONTENT_LENGTH', 'unknown'),
            'sessions_count': len(sessions)
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'pythonocc_available': HAS_PYTHONOCC,
            'ezdxf_available': HAS_EZDXF
        }), 500

@app.route('/api/upload', methods=['POST'])
def upload_step_file():
    """Upload and process STEP file"""
    try:
        print("Upload request received")
        
        if 'file' not in request.files:
            print("No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        print(f"File received: {file.filename}")
        
        if file.filename == '':
            print("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith(('.step', '.stp')):
            print(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Only STEP files (.step, .stp) are allowed'}), 400
        
        # Process STEP file directly from memory
        session_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        print(f"Processing STEP file directly from memory: {filename}")
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.step') as temp_file:
            # Write file content directly to temporary file
            file.seek(0)  # Reset file pointer to beginning
            temp_file.write(file.read())
            temp_file.flush()  # Ensure content is written to disk
            temp_file_path = temp_file.name
        
        try:
            processor = STEPProcessor()
            result = processor.load_step_file(temp_file_path)
            print(f"Processing result: {result}")
            
            # Store session data (without file_path since we're not keeping it)
            sessions[session_id] = {
                'processor': processor,
                'filename': filename
            }
            
        finally:
            # Clean up temporary file immediately after processing
            try:
                os.unlink(temp_file_path)
                print(f"Temporary file {temp_file_path} deleted")
            except OSError:
                pass
        
        result['session_id'] = session_id
        print(f"Returning result: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-face/<session_id>/<int:face_id>')
def export_face(session_id, face_id):
    """Export selected face to DXF or SVG"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    # Get format parameter (default to DXF)
    format_type = request.args.get('format', 'dxf').lower()
    
    try:
        processor = sessions[session_id]['processor']
        
        if format_type == 'svg':
            export_file = processor.export_face_to_svg(face_id)
            filename = sessions[session_id]['filename']
            base_name = os.path.splitext(filename)[0]
            download_name = f"{base_name}_face_{face_id + 1}.svg"
            mimetype = 'image/svg+xml'
        else:
            export_file, line_count = processor.export_face_to_dxf(face_id)
            filename = sessions[session_id]['filename']
            base_name = os.path.splitext(filename)[0]
            download_name = f"{base_name}_face_{face_id + 1}.dxf"
            mimetype = 'application/octet-stream'

        @after_this_request
        def remove_file(response):
            try:
                os.remove(export_file)
            except Exception as e:
                print(f"Error deleting temp file: {e}")
            return response

        return send_file(
            export_file,
            as_attachment=True,
            download_name=download_name,
            mimetype=mimetype
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/face-info/<session_id>/<int:face_id>')
def get_face_info(session_id, face_id):
    """Get detailed information about a specific face"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    try:
        processor = sessions[session_id]['processor']
        
        if face_id >= len(processor.face_data):
            return jsonify({'error': 'Invalid face ID'}), 400
        
        face_info = processor.face_data[face_id]
        return jsonify(face_info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def get_status():
    """Get application status"""
    return jsonify({
        'pythonocc_available': HAS_PYTHONOCC,
        'ezdxf_available': HAS_EZDXF,
        'active_sessions': len(sessions)
    })

@app.route('/api/preview-dxf/<session_id>/<int:face_id>')
def preview_dxf(session_id, face_id):
    """Get DXF preview data for selected face"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    try:
        processor = sessions[session_id]['processor']
        preview_data = processor.get_dxf_preview_data(face_id)
        
        return jsonify({
            'success': True,
            'preview': preview_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-dxf')
def create_test_dxf_download():
    """Create and download a test DXF file for verification"""
    try:
        processor = STEPProcessor()
        dxf_file, entity_count = processor.create_test_dxf()
        
        @after_this_request
        def remove_file(response):
            try:
                os.remove(dxf_file)
            except Exception as e:
                print(f"Error deleting temp file: {e}")
            return response

        return send_file(
            dxf_file,
            as_attachment=True,
            download_name="test_dxf_export.dxf",
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=== STEP to DXF Web Application ===")
    print(f"pythonocc-core: {'✓' if HAS_PYTHONOCC else '✗'}")
    print(f"ezdxf: {'✓' if HAS_EZDXF else '✗'}")
    print()
    print("Web Application Features:")
    print("- Drag & drop STEP file upload")
    print("- Interactive 3D viewer with Three.js")
    print("- Hover for yellow highlight")
    print("- Click for red selection")
    print("- One-click DXF export")
    print("- Responsive web interface")
    print()
    print("Access the application at:")
    print("  Local:    http://localhost:5000")
    print("  Network:  http://0.0.0.0:5000")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    print("Starting web server...")
    
    # Render deployment configuration
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
<<<<<<< HEAD
    app.run(debug=debug_mode, host='0.0.0.0', port=port, threaded=True, use_reloader=False)
=======
    app.run(debug=debug_mode, host='0.0.0.0', port=port, threaded=True, use_reloader=False)
>>>>>>> 71440361357331a598aad7874ae4bb928c8fe34e
