import itertools

import pytest
import numpy as np
import pandas as pd
import geopandas as gp
import folium as fl

from .context import gtfs_kit, cairns, cairns_shapeless, cairns_dates, cairns_trip_stats
from gtfs_kit import routes as gkr


@pytest.mark.slow
def test_compute_route_stats_0():
    feed = cairns.copy()
    ts1 = cairns_trip_stats.copy()
    ts2 = cairns_trip_stats.copy()
    ts2.direction_id = np.nan

    for ts, split_directions in itertools.product([ts1, ts2], [True, False]):
        if split_directions and ts.direction_id.isnull().all():
            # Should raise an error
            with pytest.raises(ValueError):
                gkr.compute_route_stats_0(ts, split_directions=split_directions)
            continue

        rs = gkr.compute_route_stats_0(ts, split_directions=split_directions)

        # Should be a data frame of the correct shape
        if split_directions:
            max_num_routes = 2 * feed.routes.shape[0]
        else:
            max_num_routes = feed.routes.shape[0]
        assert rs.shape[0] <= max_num_routes

        # Should contain the correct columns
        expect_cols = set(
            [
                "route_id",
                "route_short_name",
                "route_type",
                "num_trips",
                "num_trip_ends",
                "num_trip_starts",
                "is_bidirectional",
                "is_loop",
                "start_time",
                "end_time",
                "max_headway",
                "min_headway",
                "mean_headway",
                "peak_num_trips",
                "peak_start_time",
                "peak_end_time",
                "service_duration",
                "service_distance",
                "service_speed",
                "mean_trip_distance",
                "mean_trip_duration",
            ]
        )
        if split_directions:
            expect_cols.add("direction_id")
        assert set(rs.columns) == expect_cols

    # Empty check
    rs = gkr.compute_route_stats_0(pd.DataFrame(), split_directions=split_directions)
    assert rs.empty


@pytest.mark.slow
def test_compute_route_time_series_0():
    ts1 = cairns_trip_stats.copy()
    ts2 = cairns_trip_stats.copy()
    ts2.direction_id = np.nan
    for ts, split_directions in itertools.product([ts1, ts2], [True, False]):
        if split_directions and ts.direction_id.isnull().all():
            # Should raise an error
            with pytest.raises(ValueError):
                gkr.compute_route_stats_0(ts, split_directions=split_directions)
            continue

        rs = gkr.compute_route_stats_0(ts, split_directions=split_directions)
        rts = gkr.compute_route_time_series_0(
            ts, split_directions=split_directions, freq="H"
        )

        # Should be a data frame of the correct shape
        assert rts.shape[0] == 24
        assert rts.shape[1] == 6 * rs.shape[0]

        # Should have correct column names
        if split_directions:
            expect = ["indicator", "route_id", "direction_id"]
        else:
            expect = ["indicator", "route_id"]
        assert rts.columns.names == expect

        # Each route have a correct service distance total
        if not split_directions:
            g = ts.groupby("route_id")
            for route in ts["route_id"].values:
                get = rts["service_distance"][route].sum()
                expect = g.get_group(route)["distance"].sum()
                assert abs((get - expect) / expect) < 0.001

    # Empty check
    rts = gkr.compute_route_time_series_0(
        pd.DataFrame(), split_directions=split_directions, freq="1H"
    )
    assert rts.empty


def test_get_routes():
    feed = cairns.copy()
    date = cairns_dates[0]
    f = gkr.get_routes(feed, date)
    # Should have the correct shape
    assert f.shape[0] <= feed.routes.shape[0]
    assert f.shape[1] == feed.routes.shape[1]
    # Should have correct columns
    assert set(f.columns) == set(feed.routes.columns)

    g = gkr.get_routes(feed, date, "07:30:00")
    # Should have the correct shape
    assert g.shape[0] <= f.shape[0]
    assert g.shape[1] == f.shape[1]
    # Should have correct columns
    assert set(g.columns) == set(feed.routes.columns)


def test_compute_route_stats():
    feed = cairns.copy()
    dates = cairns_dates + ["20010101"]
    n = 3
    rids = feed.routes.route_id.loc[:n]
    trip_stats_subset = cairns_trip_stats.loc[lambda x: x["route_id"].isin(rids)]

    for split_directions in [True, False]:
        rs = gkr.compute_route_stats(
            feed, trip_stats_subset, dates, split_directions=split_directions
        )

        # Should be a data frame of the correct shape
        assert isinstance(rs, pd.core.frame.DataFrame)
        if split_directions:
            max_num_routes = 2 * n
        else:
            max_num_routes = n

        assert rs.shape[0] <= 2 * max_num_routes

        # Should contain the correct columns
        expect_cols = {
            "date",
            "route_id",
            "route_short_name",
            "route_type",
            "num_trips",
            "num_trip_ends",
            "num_trip_starts",
            "is_bidirectional",
            "is_loop",
            "start_time",
            "end_time",
            "max_headway",
            "min_headway",
            "mean_headway",
            "peak_num_trips",
            "peak_start_time",
            "peak_end_time",
            "service_duration",
            "service_distance",
            "service_speed",
            "mean_trip_distance",
            "mean_trip_duration",
        }
        if split_directions:
            expect_cols.add("direction_id")

        assert set(rs.columns) == expect_cols

        # Should only contains valid dates
        rs.date.unique().tolist() == cairns_dates

        # Empty dates should yield empty DataFrame
        rs = gkr.compute_route_stats(
            feed, trip_stats_subset, [], split_directions=split_directions
        )
        assert rs.empty


def test_build_zero_route_time_series():
    feed = cairns.copy()
    for split_directions in [True, False]:
        if split_directions:
            expect_names = ["indicator", "route_id", "direction_id"]
            expect_shape = (2, 6 * feed.routes.shape[0] * 2)
        else:
            expect_names = ["indicator", "route_id"]
            expect_shape = (2, 6 * feed.routes.shape[0])

        f = gkr.build_zero_route_time_series(
            feed, split_directions=split_directions, freq="12H"
        )

        assert isinstance(f, pd.core.frame.DataFrame)
        assert f.shape == expect_shape
        assert f.columns.names == expect_names
        assert not f.values.any()


def test_compute_route_time_series():
    feed = cairns.copy()
    dates = cairns_dates + ["20010101"]  # Spans 3 valid dates
    n = 3
    rids = feed.routes.route_id.loc[:n]
    trip_stats_subset = cairns_trip_stats.loc[lambda x: x["route_id"].isin(rids)]

    for split_directions in [True, False]:
        rs = gkr.compute_route_stats(
            feed, trip_stats_subset, dates, split_directions=split_directions
        )
        rts = gkr.compute_route_time_series(
            feed,
            trip_stats_subset,
            dates,
            split_directions=split_directions,
            freq="12H",
        )

        # Should be a data frame of the correct shape
        assert isinstance(rts, pd.core.frame.DataFrame)
        assert rts.shape[0] == 3 * 2  # 3-date span at 12H freq
        assert rts.shape[1] == 6 * rs.shape[0] / 2

        # Should have correct column names
        if split_directions:
            expect_names = ["indicator", "route_id", "direction_id"]
        else:
            expect_names = ["indicator", "route_id"]
        assert rts.columns.names, expect_names

        # Should have correct index name
        assert rts.index.name == "datetime"

        # Each route have a correct num_trip_starts
        if not split_directions:
            rsg = rs.groupby("route_id")
            for route in rs.route_id.values:
                get = rts["num_trip_starts"][route].sum()
                expect = rsg.get_group(route)["num_trips"].sum()
                assert get == expect

        # Empty dates should yield empty DataFrame
        rts = gkr.compute_route_time_series(
            feed, trip_stats_subset, [], split_directions=split_directions
        )
        assert rts.empty


def test_build_route_timetable():
    feed = cairns.copy()
    route_id = feed.routes["route_id"].values[0]
    dates = cairns_dates + ["20010101"]
    f = gkr.build_route_timetable(feed, route_id, dates)

    # Should have the correct columns
    expect_cols = set(feed.trips.columns) | set(feed.stop_times.columns) | set(["date"])
    assert set(f.columns) == expect_cols

    # Should only have feed dates
    assert f.date.unique().tolist() == cairns_dates

    # Empty check
    f = gkr.build_route_timetable(feed, route_id, dates[2:])
    assert f.empty


def test_geometrize_routes():
    feed = cairns.copy()
    route_ids = feed.routes.route_id.loc[:1]
    g = gkr.geometrize_routes(feed, route_ids, use_utm=True)
    assert isinstance(g, gp.GeoDataFrame)
    assert g.shape[0] == len(route_ids)
    assert g.crs != "epsg:4326"

    g = gkr.geometrize_routes(feed, route_ids, split_directions=True)
    assert isinstance(g, gp.GeoDataFrame)
    assert g.shape[0] == 2 * len(route_ids)

    with pytest.raises(ValueError):
        gkr.geometrize_routes(cairns_shapeless)

    # Test from Gilles Cuyaubere
    feed = gtfs_kit.Feed(dist_units="km")
    feed.agency = pd.DataFrame(
        {"agency_id": ["agency_id_0"], "agency_name": ["agency_name_0"]}
    )
    feed.routes = pd.DataFrame(
        {
            "route_id": ["route_id_0"],
            "agency_id": ["agency_id_0"],
            "route_short_name": [None],
            "route_long_name": ["route_long_name_0"],
            "route_desc": [None],
            "route_type": [1],
            "route_url": [None],
            "route_color": [None],
            "route_text_color": [None],
        }
    )
    feed.trips = pd.DataFrame(
        {
            "route_id": ["route_id_0"],
            "service_id": ["service_id_0"],
            "trip_id": ["trip_id_0"],
            "trip_headsign": [None],
            "trip_short_name": [None],
            "direction_id": [None],
            "block_id": [None],
            "wheelchair_accessible": [None],
            "bikes_allowed": [None],
            "trip_desc": [None],
            "shape_id": ["shape_id_0"],
        }
    )
    feed.shapes = pd.DataFrame(
        {
            "shape_id": ["shape_id_0", "shape_id_0"],
            "shape_pt_lon": [2.36, 2.37],
            "shape_pt_lat": [48.82, 48.82],
            "shape_pt_sequence": [0, 1],
        }
    )
    feed.stops = pd.DataFrame(
        {
            "stop_id": ["stop_id_0", "stop_id_1"],
            "stop_name": ["stop_name_0", "stop_name_1"],
            "stop_desc": [None, None],
            "stop_lat": [48.82, 48.82],
            "stop_lon": [2.36, 2.37],
            "zone_id": [None, None],
            "stop_url": [None, None],
            "location_type": [0, 0],
            "parent_station": [None, None],
            "wheelchair_boarding": [None, None],
        }
    )
    feed.stop_times = pd.DataFrame(
        {
            "trip_id": ["trip_id_0", "trip_id_0"],
            "arrival_time": ["11:40:00", "11:45:00"],
            "departure_time": ["11:40:00", "11:45:00"],
            "stop_id": ["stop_id_0", "stop_id_1"],
            "stop_sequence": [0, 1],
            "stop_time_desc": [None, None],
            "pickup_type": [None, None],
            "drop_off_type": [None, None],
        }
    )

    g = gkr.geometrize_routes(feed)
    assert isinstance(g, gp.GeoDataFrame)


def test_routes_to_geojson():
    feed = cairns.copy()
    route_ids = feed.routes.route_id.loc[:1]
    n = len(route_ids)

    gj = gkr.routes_to_geojson(feed, route_ids)
    assert len(gj["features"]) == n

    gj = gkr.routes_to_geojson(feed, route_ids, include_stops=True)
    k = (
        feed.stop_times.merge(feed.trips.filter(["trip_id", "route_id"]))
        .loc[lambda x: x.route_id.isin(route_ids), "stop_id"]
        .nunique()
    )
    assert len(gj["features"]) == n + k

    with pytest.raises(ValueError):
        gkr.routes_to_geojson(cairns_shapeless)

    with pytest.raises(ValueError):
        gkr.routes_to_geojson(cairns, route_ids=["bingo"])


def test_map_routes():
    feed = cairns.copy()
    rids = feed.routes.route_id.loc[:1]
    m = gkr.map_routes(feed, rids, include_stops=True)
    assert isinstance(m, fl.Map)
