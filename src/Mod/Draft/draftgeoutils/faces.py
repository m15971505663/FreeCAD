# ***************************************************************************
# *   Copyright (c) 2009, 2010 Yorik van Havre <yorik@uncreated.net>        *
# *   Copyright (c) 2009, 2010 Ken Cline <cline@frii.com>                   *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************
"""Provides various functions for working with faces."""
## @package faces
# \ingroup DRAFTGEOUTILS
# \brief Provides various functions for working with faces.

import lazy_loader.lazy_loader as lz

import DraftVecUtils

from draftgeoutils.general import precision

# Delay import of module until first use because it is heavy
Part = lz.LazyLoader("Part", globals(), "Part")


def concatenate(shape):
    """Turn several faces into one."""
    edges = getBoundary(shape)
    edges = Part.__sortEdges__(edges)
    try:
        wire = Part.Wire(edges)
        face = Part.Face(wire)
    except Part.OCCError:
        print("DraftGeomUtils: Couldn't join faces into one")
        return shape
    else:
        if not wire.isClosed():
            return wire
        else:
            return face


def getBoundary(shape):
    """Return the boundary edges of a group of faces."""
    if isinstance(shape, list):
        shape = Part.makeCompound(shape)

    # Make a lookup-table where we get the number of occurrences
    # to each edge in the fused face
    table = dict()
    for f in shape.Faces:
        for e in f.Edges:
            hash_code = e.hashCode()
            if hash_code in table:
                table[hash_code] = table[hash_code] + 1
            else:
                table[hash_code] = 1

    # Filter out the edges shared by more than one sub-face
    bound = list()
    for e in shape.Edges:
        if table[e.hashCode()] == 1:
            bound.append(e)
    return bound


def isCoplanar(faces, tolerance=0):
    """Return True if all faces in the given list are coplanar.

    Tolerance is the maximum deviation to be considered coplanar.
    """
    if len(faces) < 2:
        return True

    base = faces[0].normalAt(0, 0)

    for i in range(1, len(faces)):
        for v in faces[i].Vertexes:
            chord = v.Point.sub(faces[0].Vertexes[0].Point)
            dist = DraftVecUtils.project(chord, base)
            if round(dist.Length, precision()) > tolerance:
                return False
    return True


def bind(w1, w2):
    """Bind 2 wires by their endpoints and returns a face."""
    if not w1 or not w2:
        print("DraftGeomUtils: unable to bind wires")
        return None

    if w1.isClosed() and w2.isClosed():
        d1 = w1.BoundBox.DiagonalLength
        d2 = w2.BoundBox.DiagonalLength
        if d1 > d2:
            # w2.reverse()
            return Part.Face([w1, w2])
        else:
            # w1.reverse()
            return Part.Face([w2, w1])
    else:
        try:
            w3 = Part.LineSegment(w1.Vertexes[0].Point,
                                  w2.Vertexes[0].Point).toShape()
            w4 = Part.LineSegment(w1.Vertexes[-1].Point,
                                  w2.Vertexes[-1].Point).toShape()
            return Part.Face(Part.Wire(w1.Edges+[w3] + w2.Edges+[w4]))
        except Part.OCCError:
            print("DraftGeomUtils: unable to bind wires")
            return None


def cleanFaces(shape):
    """Remove inner edges from coplanar faces."""
    faceset = shape.Faces

    def find(hc):
        """Find a face with the given hashcode."""
        for f in faceset:
            if f.hashCode() == hc:
                return f

    def findNeighbour(hface, hfacelist):
        """Find the first neighbour of a face, and return its index."""
        eset = []
        for e in find(hface).Edges:
            eset.append(e.hashCode())
        for i in range(len(hfacelist)):
            for ee in find(hfacelist[i]).Edges:
                if ee.hashCode() in eset:
                    return i
        return None

    # build lookup table
    lut = {}
    for face in faceset:
        for edge in face.Edges:
            if edge.hashCode() in lut:
                lut[edge.hashCode()].append(face.hashCode())
            else:
                lut[edge.hashCode()] = [face.hashCode()]

    # print("lut:",lut)
    # take edges shared by 2 faces
    sharedhedges = []
    for k, v in lut.items():
        if len(v) == 2:
            sharedhedges.append(k)

    # print(len(sharedhedges)," shared edges:",sharedhedges)
    # find those with same normals
    targethedges = []
    for hedge in sharedhedges:
        faces = lut[hedge]
        n1 = find(faces[0]).normalAt(0.5, 0.5)
        n2 = find(faces[1]).normalAt(0.5, 0.5)
        if n1 == n2:
            targethedges.append(hedge)

    # print(len(targethedges)," target edges:",targethedges)
    # get target faces
    hfaces = []
    for hedge in targethedges:
        for f in lut[hedge]:
            if f not in hfaces:
                hfaces.append(f)

    # print(len(hfaces)," target faces:",hfaces)
    # sort islands
    islands = [[hfaces.pop(0)]]
    currentisle = 0
    currentface = 0
    found = True
    while hfaces:
        if not found:
            if len(islands[currentisle]) > (currentface + 1):
                currentface += 1
                found = True
            else:
                islands.append([hfaces.pop(0)])
                currentisle += 1
                currentface = 0
                found = True
        else:
            f = findNeighbour(islands[currentisle][currentface], hfaces)
            if f is not None:
                islands[currentisle].append(hfaces.pop(f))
            else:
                found = False

    # print(len(islands)," islands:",islands)
    # make new faces from islands
    newfaces = []
    treated = []
    for isle in islands:
        treated.extend(isle)
        fset = []
        for i in isle:
            fset.append(find(i))
        bounds = getBoundary(fset)
        shp = Part.Wire(Part.__sortEdges__(bounds))
        shp = Part.Face(shp)
        if shp.normalAt(0.5, 0.5) != find(isle[0]).normalAt(0.5, 0.5):
            shp.reverse()
        newfaces.append(shp)

    # print("new faces:",newfaces)
    # add remaining faces
    for f in faceset:
        if not f.hashCode() in treated:
            newfaces.append(f)

    # print("final faces")
    # finishing
    fshape = Part.makeShell(newfaces)
    if shape.isClosed():
        fshape = Part.makeSolid(fshape)
    return fshape


def removeSplitter(shape):
    """Return a face from removing the splitter in a list of faces.

    This is an alternative, shared edge-based version of Part.removeSplitter.
    Returns a face, or `None` if the operation failed.
    """
    lookup = dict()
    for f in shape.Faces:
        for e in f.Edges:
            h = e.hashCode()
            if h in lookup:
                lookup[h].append(e)
            else:
                lookup[h] = [e]

    edges = [e[0] for e in lookup.values() if len(e) == 1]

    try:
        face = Part.Face(Part.Wire(edges))
    except Part.OCCError:
        # operation failed
        return None
    else:
        if face.isValid():
            return face

    return None
