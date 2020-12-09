# -*- coding: utf-8 -*-

import cartopy.crs as ccrs
import ESMF
import numpy as np


class GridInfo:
    """
    TBD: public class docstring summary (one line).

    This class holds information about lat-lon type grids. That is, grids
    defined by lists of latitude and longitude values for points/bounds
    (with respect to some coordinate reference system i.e. rotated pole).
    It contains methods for translating this information into ESMF objects.
    In particular, there are methods for representing as an ESMF Grid and
    as an ESMF Field containing that Grid. This ESMF Field is designed to
    contain enough information for area weighted regridding and may be
    inappropriate for other ESMF regridding schemes.

    """

    # TODO: Edit GridInfo so that it is able to handle 2D lat/lon arrays.

    def __init__(
        self,
        lons,
        lats,
        lonbounds,
        latbounds,
        crs=None,
        circular=False,
        areas=None,
    ):
        """
        Create a GridInfo object describing the grid.

        Parameters
        ----------
        lons : array_like
            A 1D numpy array or list describing the longitudes of the
            grid points.
        lats : array_like
            A 1D numpy array or list describing the latitudes of the
            grid points.
        lonbounds : array_like
            A 1D numpy array or list describing the longitude bounds of
            the grid. Should have length one greater than lons.
        latbounds : array_like
            A 1D numpy array or list describing the latitude bounds of
            the grid. Should have length one greater than lats.
        crs : cartopy projection, optional
            None or a cartopy.crs projection describing how to interpret the
            above arguments. If None, defaults to Geodetic().
        circular : bool, optional
            A boolean value describing if the final longitude bounds should
            be considered contiguous with the first. Defaults to False.
        areas : array_line, optional
            either None or a numpy array describing the areas associated with
            each face. If None, then ESMF will use its own calculated areas.

        """
        self.lons = lons
        self.lats = lats
        self.lonbounds = lonbounds
        self.latbounds = latbounds
        if crs is None:
            self.crs = ccrs.Geodetic()
        else:
            self.crs = crs
        self.circular = circular
        self.areas = areas

    def _as_esmf_info(self):
        shape = np.array([len(self.lats), len(self.lons)])

        if self.circular:
            adjustedlonbounds = self.lonbounds[:-1]
        else:
            adjustedlonbounds = self.lonbounds

        centerlons, centerlats = np.meshgrid(self.lons, self.lats)
        cornerlons, cornerlats = np.meshgrid(adjustedlonbounds, self.latbounds)

        truecenters = ccrs.Geodetic().transform_points(self.crs, centerlons, centerlats)
        truecorners = ccrs.Geodetic().transform_points(self.crs, cornerlons, cornerlats)

        # The following note in xESMF suggests that the arrays passed to ESMPy ought to
        # be fortran ordered:
        # https://xesmf.readthedocs.io/en/latest/internal_api.html#xesmf.backend.warn_f_contiguous
        # It is yet to be determined what effect this has on performance.
        truecenterlons = np.asfortranarray(truecenters[..., 0])
        truecenterlats = np.asfortranarray(truecenters[..., 1])
        truecornerlons = np.asfortranarray(truecorners[..., 0])
        truecornerlats = np.asfortranarray(truecorners[..., 1])

        info = (
            shape,
            truecenterlons,
            truecenterlats,
            truecornerlons,
            truecornerlats,
            self.circular,
            self.areas,
        )
        return info

    def _make_esmf_grid(self):
        info = self._as_esmf_info()
        (
            shape,
            truecenterlons,
            truecenterlats,
            truecornerlons,
            truecornerlats,
            circular,
            areas,
        ) = info

        if circular:
            grid = ESMF.Grid(
                shape,
                pole_kind=[1, 1],
                num_peri_dims=1,
                periodic_dim=1,
                pole_dim=0,
            )
        else:
            grid = ESMF.Grid(shape, pole_kind=[1, 1])

        grid.add_coords(staggerloc=ESMF.StaggerLoc.CORNER)
        grid_corner_x = grid.get_coords(0, staggerloc=ESMF.StaggerLoc.CORNER)
        grid_corner_x[:] = truecornerlons
        grid_corner_y = grid.get_coords(1, staggerloc=ESMF.StaggerLoc.CORNER)
        grid_corner_y[:] = truecornerlats

        # Grid center points would be added here, this is not necessary for
        # conservative area weighted regridding
        # grid.add_coords(staggerloc=ESMF.StaggerLoc.CENTER)
        # grid_center_x = grid.get_coords(0, staggerloc=ESMF.StaggerLoc.CENTER)
        # grid_center_x[:] = truecenterlons
        # grid_center_y = grid.get_coords(1, staggerloc=ESMF.StaggerLoc.CENTER)
        # grid_center_y[:] = truecenterlats

        if areas is not None:
            grid.add_item(ESMF.GridItem.AREA, staggerloc=ESMF.StaggerLoc.CENTER)
            grid_areas = grid.get_item(
                ESMF.GridItem.AREA, staggerloc=ESMF.StaggerLoc.CENTER
            )
            grid_areas[:] = areas.T

        return grid

    def make_esmf_field(self):
        """TBD: public method docstring."""
        grid = self._make_esmf_grid()
        field = ESMF.Field(grid, staggerloc=ESMF.StaggerLoc.CENTER)
        return field

    def size(self):
        """TBD: public method docstring."""
        return len(self.lons) * len(self.lats)

    def _index_offset(self):
        return 1

    def _flatten_array(self, array):
        return array.flatten()

    def _unflatten_array(self, array):
        return array.reshape((len(self.lons), len(self.lats)))