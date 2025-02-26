#!/usr/bin/env python
'''
Copyright (C) 2005,2007 Aaron Spike, aaron@ekips.org
- template dxf_outlines.dxf added Feb 2008 by Alvin Penner, penner@vaxxine.com
- layers, transformation, flattening added April 2008 by Bob Cook, bob@bobcookdev.com
- improved layering support added Feb 2009 by T. R. Gipson, drmn4ea at google mail
- (1.1.2) updated due to deprication warnings etc. Now Inkscape 1.1 compatible. Oct 2021 by Axel Sylvester bbdfx at fablab-hamburg.org#
- (1.2) updated to Inkscape 2.x, fix scaling issue, export to layer0. Dec 2023 Andreas Kahler andreas at fablab-muenchen.de

TODO: shapes like Rectangle, Circle, Ellipse are currently ignored
TODO: simpletransform still uses a stand-alone version of cubicsuperpath. Maybe this can be replaced by CubicSuperPath(d) of inkex.paths?

Associated files:
b2_dxf_outlines.py: this file with the main program
b2r_dxf_outlines.inx: Inkscape extension definition. This is makes the extension appear in the file-type selector of the save dialog.
dxf_templates_b2.py: Something like the DXF File template. Contains variables with DXF parts (e.g. header and footer).
simpletransform.py: Defines several functions to make handling of transform
attribute easier. 

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

import inkex, simpletransform, dxf_templates_b2, re


# define the class of this extension to be a child of inkex.OutputExtension
# The Inkscape will automatically call the function save() when you execute the extension.

class Bb2DXF(inkex.OutputExtension):

    def __init__(self):
        super(Bb2DXF, self).__init__()
        self.__version__ = "1.2"
        self.dxf = ''
        self.handle = 255
        self.flatness = 0.1

    
        
    def save(self, stream):
        self._stream = stream
        # Stream needs to be in binary format (a bytes-like object is required, not 'str'). Probably because Inkscape opened the output file with "wb" mode. 
        # At least on Unix systems it works when you encode prepared dxf as utf-8.
        stream.write(self.dxf.encode('utf-8'))
        
    
    
    def dxf_add(self, str):
        self.dxf += str

    def dxf_insert_code(self, code, value):
        self.dxf += code + "\n" + value + "\n"

    def dxf_line(self,layer,csp):
        self.dxf_insert_code(   '0', 'LINE' )
        self.dxf_insert_code(   '8', layer )
        self.dxf_insert_code(  '62', '4' )
        self.dxf_insert_code(   '5', '%x' % self.handle )
        self.dxf_insert_code( '100', 'AcDbEntity' )
        self.dxf_insert_code( '100', 'AcDbLine' )
        self.dxf_insert_code(  '10', '%f' % csp[0][0] )
        self.dxf_insert_code(  '20', '%f' % csp[0][1] )
        self.dxf_insert_code(  '30', '0.0' )
        self.dxf_insert_code(  '11', '%f' % csp[1][0] )
        self.dxf_insert_code(  '21', '%f' % csp[1][1] )
        self.dxf_insert_code(  '31', '0.0' )

    def dxf_point(self,layer,x,y):
        self.dxf_insert_code(   '0', 'POINT' )
        self.dxf_insert_code(   '8', layer )
        self.dxf_insert_code(  '62', '4' )
        self.dxf_insert_code(   '5', '%x' % self.handle )
        self.dxf_insert_code( '100', 'AcDbEntity' )
        self.dxf_insert_code( '100', 'AcDbPoint' )
        self.dxf_insert_code(  '10', '%f' % x )
        self.dxf_insert_code(  '20', '%f' % y )
        self.dxf_insert_code(  '30', '0.0' )

    def dxf_path_to_lines(self,layer,p):
        f = self.flatness
        is_flat = 0
        while is_flat < 1:
            try:
                inkex.bezier.cspsubdiv(p, self.flatness)
                is_flat = 1
            except:
                f += 0.1

        for sub in p:
            for i in range(len(sub)-1):
                self.handle += 1
                s = sub[i]
                e = sub[i+1]
                self.dxf_line(layer,[s[1],e[1]])

    def dxf_path_to_point(self,layer,p):
        bbox = simpletransform.roughBBox(p)
        x = (bbox[0] + bbox[1]) / 2
        y = (bbox[2] + bbox[3]) / 2
        self.dxf_point(layer,x,y)

    def effect(self):
        svg_version = self.document.getroot().xpath("@id",namespaces=inkex.NSS)[0]
        
        #self.dxf_insert_code( '1001',  str(svg_version))
        #self.dxf_insert_code( '1000',  str(svg_version=="svg2"))
        
        # at least if document unit is set to mm
        
        if str(svg_version)=="svg2":
             svgBase='on old inkscape svg file'
             #self.dxf_insert_code( '1000',  svgBase)
             # Older (0.x) Versions of Inkscape needed this scaling factor
             # at least if document unit is set to mm
             scale = 25.4/90.0
        else:
             svgBase = 'Inkscape svg file'
             scale = self.svg.viewport_to_unit(1, unit="mm")

        self.dxf_insert_code( '999', 
            'Inkscape export of an ' + svgBase + ' via Better Better DXF Output 2023. ' +    
            'https://github.com/drayde/InkscapeExtension_BetterBetterDXFOutput2023'
            )
        self.dxf_add( dxf_templates_b2.r14_header )

        h = self.svg.unittouu(self.document.getroot().xpath('@height',namespaces=inkex.NSS)[0])

        path = '//svg:path'

        # run thru entire document gathering a list of layers to generate a proper DXF LAYER table. There is probably a better way to do this.
        layers=[];
        for node in self.document.getroot().xpath(path, namespaces=inkex.NSS):

            layer = node.getparent().get(inkex.addNS('label','inkscape'))
            if layer == None:
                layer = '0'

            if not layer in layers:
                layers.append(layer)

        self.dxf_insert_code('0', 'TABLE')
        self.dxf_insert_code('2', 'LAYER')
        self.dxf_insert_code('5', '2')
        self.dxf_insert_code('330', '0')
        self.dxf_insert_code('100', 'AcDbSymbolTable')
        # group code 70 tells a reader how many table records to expect (e.g. pre-allocate memory for).
        # It must be greater or equal to the actual number of records
        self.dxf_insert_code('70',str(len(layers)))

        for layer in layers:
             self.dxf_insert_code('0', 'LAYER')
             self.dxf_insert_code('5', '10')
             self.dxf_insert_code('330', '2')
             self.dxf_insert_code('100', 'AcDbSymbolTableRecord')
             self.dxf_insert_code('100', 'AcDbLayerTableRecord')
             self.dxf_insert_code('2', layer)
             self.dxf_insert_code('70', '0')
             self.dxf_insert_code('62', '7')
             self.dxf_insert_code('6', 'CONTINUOUS')

        self.dxf_insert_code('0','ENDTAB')
        self.dxf_insert_code('0','ENDSEC')
        self.dxf_add( dxf_templates_b2.r14_blocks )


        # Generate actual geometry...
        for node in self.document.getroot().xpath(path,namespaces=inkex.NSS):

            layer = node.getparent().get(inkex.addNS('label','inkscape'))
            if layer == None:
                layer = '0' # standard layer

            d = node.get('d')
            # Stand-alone cubicsuperpath is deprecated. 
            # p = cubicsuperpath.parsePath(d)
            # https://github.com/Klowner/inkscape-applytransforms/issues/21
            p = inkex.paths.CubicSuperPath(d)
            
            

            t = node.get('transform')
            if t != None:
                m = simpletransform.parseTransform(t)
                simpletransform.applyTransformToPath(m,p)

            m = [[scale,0,0],[0,-scale,h*scale]]
            simpletransform.applyTransformToPath(m,p)
            
            # CNC Machines use DXF points (not circles) as coordinates
            # for drilling. If a layername ends with drill path on that
            # layer(s) will automatically converted to points. Works best
            # with small circles or rectangles. 
            if re.search('drill$',layer,re.I) == None:
            #if layer == 'Brackets Drill':
                self.dxf_path_to_lines(layer,p)
            else:
                self.dxf_path_to_point(layer,p)

        self.dxf_add( dxf_templates_b2.r14_footer )

# run the extension
if __name__ == '__main__':
    Bb2DXF().run()
