# -*- coding: utf-8 -*-
"""
Created on Thu Mar 21 16:39:36 2019

@author: Roberto
"""
import numpy as np
import geopandas as gpd
import shapely.geometry as shp
import multiprocessing
# To avoid pandas warnings
import warnings
warnings.filterwarnings('ignore')

def envelope_generator(df_chunk, df_total, glazing_ratio_df):
    # Define local envelope
    local_envelope = gpd.GeoDataFrame(columns=['egid', 'geometry', 'class_id', 'glazing_ratio'])
    # Simplify model to take care of curves and convert it into a polygon 
    for r in df_chunk.index:
        if (isinstance(df_chunk["geometry"].loc[r], shp.multipolygon.MultiPolygon)):
            for poly in df_chunk["geometry"].loc[r]:
                try:
                    poly = poly.simplify(0.2, preserve_topology=True)
                except:
                    pass
                df_chunk["geometry"].loc[r] = poly
            else:
                try:
                    df_chunk["geometry"].loc[r] = df_chunk["geometry"].loc[r].simplify(0.2, preserve_topology=True)
                except:
                    pass
        # Check for interior rings
        df_chunk["interior"] = ''
        interiors_list = []
        for ring in df_chunk["geometry"].loc[r].interiors:
            ring_coords = list(ring.coords)
            interiors_list.append(ring_coords)
        df_chunk["interior"].loc[r] = interiors_list
    # Create the surfaces: 
    for r in df_chunk.index:
        if df_chunk.index[-1] == len(df_chunk)-1:
            print('surfacing progress: ' + str(100*r/df_chunk.index[-1]) + '%')
        # Define variables for creating the surfaces
        egid = df_chunk["egid"].loc[r]
        construction_year = df_chunk["construction_year"].loc[r] 
        altitude = df_chunk["altitude"].loc[r]
        height = df_chunk["height"].loc[r]
        if df_chunk["height"].loc[r]!= 0:
            heightalt = altitude + height
        else:
            heightalt = df_chunk["altitude"].loc[r] + 0.001           
        # Create floor:
        floorpoints = list()
        try:
            for pt in df_chunk["geometry"].loc[r].exterior.coords: 
                point = list(pt + (altitude,))
                floorpoints.append(point)
            # Take care of interior rings
            if len(df_chunk["interior"].loc[r]) == 0:
                pass
            else:
                last_points = []
                for ring in df_chunk["interior"].loc[r]:
                    ring.reverse()
                    for pt in ring:
                        intpoint = list(pt + (altitude,))
                        floorpoints.append(intpoint)
                    floorpoints = floorpoints[:-1]
                    last_point = list(ring[-1] + (altitude,))
                    notsolast_point = list(ring[-2] + (altitude,))
                    last_points.append(last_point)
                    last_points.append(notsolast_point)
                last_points = last_points[:-1]
                last_points.reverse()
                for pt in last_points:
                    floorpoints.append(pt)
            floor = shp.Polygon(floorpoints)
            surface = {"egid" : egid, "geometry" : floor, "class_id" : 33, "glazing_ratio" : 0}
            local_envelope = local_envelope.append(surface, ignore_index=True)                            
        except:
            pass
        # Create roof:
        roofpoints = list()
        try:
            for pt in df_chunk["geometry"].loc[r].exterior.coords: 
                point = list(pt + (heightalt,))
                roofpoints.append(point)
            # Take care of interior rings
            if len(df_chunk["interior"].loc[r]) == 0:
                pass
            else:
                last_points = []
                for ring in df_chunk["interior"].loc[r]:
                    ring.reverse()
                    for pt in ring:
                        intpoint = list(pt + (heightalt,))
                        roofpoints.append(intpoint)
                    roofpoints = roofpoints[:-1]
                    last_point = list(ring[-1] + (heightalt,))
                    notsolast_point = list(ring[-2] + (heightalt,))
                    last_points.append(last_point)
                    last_points.append(notsolast_point)
                last_points = last_points[:-1]
                last_points.reverse()
                for pt in last_points:
                    roofpoints.append(pt)
            roofpoints.reverse()
            roof = shp.Polygon(roofpoints)
            for r1 in glazing_ratio_df.index:
                y1 = glazing_ratio_df["period_start"].loc[r1]
                y2 = glazing_ratio_df["period_end"].loc[r1]
                class_id = glazing_ratio_df["class_id"].loc[r1]
                if y1 <= construction_year < y2 and class_id == 35:
                    glazing_ratio = glazing_ratio_df["value"].loc[r1]
            surface = {"egid" : egid, "geometry" : roof, "class_id" : 35, "glazing_ratio" : glazing_ratio}
            local_envelope = local_envelope.append(surface, ignore_index=True)                            
        except:
            pass
        # Take care of overlapping walls and create patches
        df_chunk["floor_union"] = df_chunk["geometry"]
        for j in df_total.index:
            linesect = df_total["geometry"].loc[j].intersection(df_chunk["geometry"].loc[r])
            if isinstance(linesect, shp.linestring.LineString):
                    floor_union = df_chunk["floor_union"].loc[r].union(df_total["geometry"].loc[j])
                    df_chunk["floor_union"].loc[r] = floor_union
                    if (df_chunk["height"].loc[r] + df_chunk["altitude"].loc[r]) > (df_total["height"].loc[j] + df_total["altitude"].loc[j]):
                        x_one = linesect.coords[0][0]
                        x_two = linesect.coords[1][0]
                        y_one = linesect.coords[0][1]
                        y_two = linesect.coords[1][1]
                        z_one = (df_total["height"].loc[j] + df_total["altitude"].loc[j])
                        z_two = (df_chunk["height"].loc[r] + df_chunk["altitude"].loc[r])
                        patchlist = [[x_two, y_two, z_one], [x_two, y_two, z_two], [x_one, y_one, z_two], [x_one, y_one, z_one]]
                        patchpoly = shp.Polygon(patchlist)
                        for r1 in glazing_ratio_df.index:
                            y1 = glazing_ratio_df["period_start"].loc[r1]
                            y2 = glazing_ratio_df["period_end"].loc[r1]
                            class_id = glazing_ratio_df["class_id"].loc[r1]
                            if y1 <= construction_year < y2 and class_id == 34:
                                glazing_ratio = glazing_ratio_df["value"].loc[r1]
                        surface = {"egid" : egid, "geometry" : patchpoly, "class_id" : 34, "glazing_ratio" : glazing_ratio}
                        local_envelope = local_envelope.append(surface, ignore_index=True)   
        # Create walls: 
        splitpoints = shp.MultiPoint(list(df_chunk["floor_union"].loc[r].exterior.coords))
        for i in range(len(splitpoints)-1):
            x_one = splitpoints[i].x
            x_two = splitpoints[i+1].x
            y_one = splitpoints[i].y
            y_two = splitpoints[i+1].y
            line = shp.LineString([(splitpoints[i].x, splitpoints[i].y), (splitpoints[i+1].x, splitpoints[i+1].y)])
            wallpoints = [[x_one, y_one, altitude], [x_one, y_one, heightalt], [x_two, y_two, heightalt], [x_two, y_two, altitude]]
            wall = shp.Polygon(wallpoints)
            if df_chunk["geometry"].loc[r].exterior.contains(line):
                for r1 in glazing_ratio_df.index:
                    y1 = glazing_ratio_df["period_start"].loc[r1]
                    y2 = glazing_ratio_df["period_end"].loc[r1]
                    class_id = glazing_ratio_df["class_id"].loc[r1]
                    if y1 <= construction_year < y2 and class_id == 34:
                        glazing_ratio = glazing_ratio_df["value"].loc[r1]
                surface = {"egid" : egid, "geometry" : wall, "class_id" : 34, "glazing_ratio" : glazing_ratio} 
                local_envelope = local_envelope.append(surface, ignore_index=True)
        # Create interior walls
        for ring in df_chunk["interior"].loc[r]:
            for i in range(len(ring)-1):
                x_one = ring[i][0]
                x_two = ring[i+1][0]
                y_one = ring[i][1]
                y_two = ring[i+1][1]
                wallpoints = [[x_one, y_one, altitude], [x_one, y_one, heightalt], [x_two, y_two, heightalt], [x_two, y_two, altitude]]
                wallpoints.reverse()
                wall = shp.Polygon(wallpoints)
                for r1 in glazing_ratio_df.index:
                    y1 = glazing_ratio_df["period_start"].loc[r1]
                    y2 = glazing_ratio_df["period_end"].loc[r1]
                    class_id = glazing_ratio_df["class_id"].loc[r1]
                    if y1 <= construction_year < y2 and class_id == 34:
                        glazing_ratio = glazing_ratio_df["value"].loc[r1]
                surface = {"egid" : egid, "geometry" : wall, "class_id" : 34, "glazing_ratio" : glazing_ratio}
                local_envelope = local_envelope.append(surface, ignore_index=True)
    return local_envelope 


def eg_run(buildings_df, glazing_ratio_df):
    df_length = len(buildings_df)
    envelope = gpd.GeoDataFrame(columns=['egid', 'geometry', 'class_id'])
    # Create as many processes as there are CPUs on the machine - 1
    num_processes = min(multiprocessing.cpu_count()-1, df_length)
    # Calculate the chunk size as an integer
    chunk_size = int(np.ceil(df_length/num_processes))
    # Divide the df in chunks
    chunks = [buildings_df.iloc[buildings_df.index[i:i + chunk_size]] for i in range(0, df_length, chunk_size)]
    # Create a pool of processes
    pool = multiprocessing.Pool(processes=num_processes)   
    # Apply the function to the chunks and combine the results in a single df
    for result in pool.starmap(envelope_generator, [(i, buildings_df, glazing_ratio_df) for i in chunks]):
        envelope = envelope.append(result, ignore_index = True) 
    pool.close()
    pool.join()
    return envelope

def buildings_xml(df_chunk, envelope, occupancy_df):
    text = ''
    for r in df_chunk.index:
        if df_chunk.index[-1] == len(df_chunk)-1:
            print('printing progress: ' + str(100*r/df_chunk.index[-1]) + '%')
        egid = df_chunk["egid"].loc[r]
        ssid = df_chunk["ssid"].loc[r]
        occupancy_type = df_chunk["occupancytype"].loc[r]
        height = df_chunk["height"].loc[r]
        gross_volume = df_chunk["gross_volume"].loc[r]
        n_people = df_chunk["n_people"].loc[r]
        n_floors = int(df_chunk["n_floors"].loc[r])
        ventilation_coeff = occupancy_df["ventilation_coeff"].loc[occupancy_type-1]
        nat_ventilation_coeff = occupancy_df["nat_ventilation_coeff"].loc[occupancy_type-1]
        ventilation_rate = occupancy_df["ventilation_rate"].loc[occupancy_type-1]*ventilation_coeff*(n_floors/height)
        infiltration_rate = df_chunk["infiltration_rate"].loc[r]*nat_ventilation_coeff
        ventilation = max(ventilation_rate, infiltration_rate)
        surfaces_df = envelope.loc[envelope['egid'] == egid]
        if occupancy_type == 1:
            dhwtype = 1
        else:
            dhwtype = 2
        text = text + '<Building id="' + str(ssid) + '" key="' + str(egid) + '" Vi="' + str(gross_volume) + '" Ninf="' + str(ventilation) + '" Tmin="21.0" Tmax="26.0" BlindsLambda="0.0170000009" BlindsIrradianceCutOff="300.0" Simulate="true">\n'
        text = text + '<HeatTank V="50.0" phi="200.0" rho="1000.0" Cp="4180.0" Tmin="20.0" Tmax="35.0" Tcritical="90.0"/>\n'
        text = text + '<DHWTank V="0.2" phi="2.5" rho="1000.0" Cp="4180.0" Tmin="50.0" Tmax="70.0" Tcritical="90.0" Tinlet="5.0"/>\n'
        text = text + '<CoolTank V="20.0" phi="20.0" rho="1000.0" Cp="4180.0" Tmin="5.0" Tmax="20.0"/>\n'
        text = text + '<HeatSource beginDay="288" endDay="135">\n'
        text = text + '<Boiler name = "boiler1" Pmax="500000" eta_th="0.96"/>\n'
        text = text + '</HeatSource>\n'
        text = text + '<Zone id="' + str(r) + '" volume="' + str(gross_volume*0.8) + '" Psi="0.2" groundFloor="true">\n'
        text = text + '<Occupants n="'+ str(n_people) + '" type ="' + str(occupancy_type) + '" Stochastic="true" activityType="11" DHWType="' + str(dhwtype) + '"/>\n'
        for r1 in surfaces_df.index:
            surface = surfaces_df["geometry"].loc[r1]
            class_id = surfaces_df["class_id"].loc[r1]
            glazing_ratio = surfaces_df["glazing_ratio"].loc[r1]
            composite_id = surfaces_df["composite_id"].loc[r1]
            if class_id == 34:
                text = text + '<Wall id="' + str(r1) + '" type="'+ str(composite_id) +'" ShortWaveReflectance="0.2" GlazingRatio="' + str(glazing_ratio) + '" GlazingGValue="0.47" GlazingUValue="3.3" OpenableRatio="0.5">\n'
                v = 0
                for n in range(len(surface.exterior.coords)-1):
                    text = text + '<V' + str(v) +' x="' + str(surface.exterior.coords[n][0]) + '" y="' + str(surface.exterior.coords[n][1]) + '" z="' + str(surface.exterior.coords[n][2]) + '"/>\n'
                    v = v + 1
                text = text + '</Wall>\n'
            elif class_id == 33:
                text = text + '<Floor id="' + str(r1) + '" type="'+ str(composite_id) +'">\n'
                v = 0
                for n in range(len(surface.exterior.coords)-1):
                    text = text + '<V' + str(v) +' x="' + str(surface.exterior.coords[n][0]) + '" y="' + str(surface.exterior.coords[n][1]) + '" z="' + str(surface.exterior.coords[n][2]) + '"/>\n'
                    v = v + 1
                text = text + "</Floor>\n"
            elif class_id == 35:
                text = text + '<Roof id="' + str(r1) + '" type="'+ str(composite_id) +'" ShortWaveReflectance="0.2" GlazingRatio="' + str(glazing_ratio) + '" GlazingGValue="0.7" GlazingUValue="1.4" OpenableRatio="0.0">\n'
                v = 0
                for n in range(len(surface.exterior.coords)-1):
                    text = text + '<V' + str(v) +' x="' + str(surface.exterior.coords[n][0]) + '" y="' + str(surface.exterior.coords[n][1]) + '" z="' + str(surface.exterior.coords[n][2]) + '"/>\n'
                    v = v + 1
                text = text + '</Roof>\n'             
        text = text + '</Zone>\n'
        text = text + '</Building>\n'
    return text
       
    
def bx_run(buildings_df, envelope, occupancy_df):
    df_length = len(buildings_df)
    # Create as many processes as there are CPUs on the machine
    num_processes = min(multiprocessing.cpu_count()-1, df_length)
    # Calculate the chunk size as an integer
    chunk_size = int(np.ceil(df_length/num_processes))
    # Divide the df in chunks
    chunks = [buildings_df.iloc[buildings_df.index[i:i + chunk_size]] for i in range(0, df_length, chunk_size)]
    # Create a pool of processes
    pool = multiprocessing.Pool(processes=num_processes)   
    # Apply the function to the chunks and combine the results in a single variable
    text = ''
    for result in pool.starmap(buildings_xml, [(i, envelope, occupancy_df) for i in chunks]):
        text = text + result    
    pool.close()
    pool.join()
    return text