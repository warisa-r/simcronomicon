import pytest
import h5py
import tempfile
import os
import json
import warnings
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from unittest.mock import patch, MagicMock

from simcronomicon import Town, TownParameters, Simulation
from simcronomicon.visualization import plot_status_summary_from_hdf5, plot_scatter
from test.test_helper import MODEL_MATRIX, default_test_step_events, setup_simulation, create_test_town_files

# Use non-interactive backend for matplotlib in tests
matplotlib.use('Agg')


class TestPlotStatusSummary:

    @pytest.mark.parametrize("model_key", ["seir", "seisir", "seiqrdv"])
    def test_plot_status_summary_all_statuses(self, model_key):
        with tempfile.TemporaryDirectory() as tmpdir:
            town_params = TownParameters(num_pop=50, num_init_spreader=5)
            folk_class = MODEL_MATRIX[model_key][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                model_key, town_params, step_events=step_events, timesteps=10, seed=True)

            h5_path = os.path.join(tmpdir, "test_plot.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            # Mock plt.show() to prevent actual display during testing
            with patch('matplotlib.pyplot.show') as mock_show:
                plot_status_summary_from_hdf5(h5_path)
                mock_show.assert_called_once()

    @pytest.mark.parametrize("model_key,status", [
        ("seir", "S"),
        ("seir", "I"),
        ("seisir", "Is"),
        ("seiqrdv", "V")
    ])
    def test_plot_status_summary_single_status(self, model_key, status):
        with tempfile.TemporaryDirectory() as tmpdir:
            town_params = TownParameters(num_pop=50, num_init_spreader=5)
            folk_class = MODEL_MATRIX[model_key][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                model_key, town_params, step_events=step_events, timesteps=10, seed=True)

            h5_path = os.path.join(tmpdir, "test_single_status.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            with patch('matplotlib.pyplot.show') as mock_show:
                plot_status_summary_from_hdf5(h5_path, status_type=status)
                mock_show.assert_called_once()

    @pytest.mark.parametrize("model_key,status_list", [
        ("seir", ["S", "I"]),
        ("seisir", ["Is", "Ir"]),
        ("seiqrdv", ["S", "V", "D"])
    ])
    def test_plot_status_summary_multiple_statuses(
            self, model_key, status_list):
        with tempfile.TemporaryDirectory() as tmpdir:
            town_params = TownParameters(num_pop=50, num_init_spreader=5)
            folk_class = MODEL_MATRIX[model_key][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                model_key, town_params, step_events=step_events, timesteps=10, seed=True)

            h5_path = os.path.join(tmpdir, "test_multiple_status.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            with patch('matplotlib.pyplot.show') as mock_show:
                plot_status_summary_from_hdf5(
                    h5_path, status_type=status_list)
                mock_show.assert_called_once()

    def test_plot_status_summary_invalid_status_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            town_params = TownParameters(num_pop=50, num_init_spreader=5)
            folk_class = MODEL_MATRIX["seir"][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                "seir", town_params, step_events=step_events, timesteps=10, seed=True)

            h5_path = os.path.join(tmpdir, "test_invalid.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            # Test invalid string
            with pytest.raises(ValueError, match="Invalid status_type 'INVALID'"):
                plot_status_summary_from_hdf5(
                    h5_path, status_type="INVALID")

            # Test invalid list
            with pytest.raises(ValueError, match="Invalid status types"):
                plot_status_summary_from_hdf5(
                    h5_path, status_type=["S", "INVALID"])

            # Test invalid type
            with pytest.raises(TypeError, match="status_type must be None, str, or list of str"):
                plot_status_summary_from_hdf5(h5_path, status_type=123)

    def test_plot_status_summary_empty_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_h5_path = os.path.join(tmpdir, "empty.h5")

            # Create empty HDF5 file with proper structure but no data
            with h5py.File(empty_h5_path, "w") as h5file:
                status_group = h5file.create_group("status_summary")
                # Create empty dataset with proper dtype
                dt = [('timestep', 'i4'), ('S', 'i4'), ('I', 'i4')]
                status_group.create_dataset("summary", (0,), dtype=dt)

                # Add required config
                config_group = h5file.create_group("config")
                sim_config = {"population": 100}
                config_group.create_dataset(
                    "simulation_config",
                    data=json.dumps(sim_config).encode("utf-8")
                )

            with pytest.raises(ValueError, match="No status data found in HDF5 file"):
                plot_status_summary_from_hdf5(empty_h5_path)

    def test_plot_status_summary_zero_population(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zero_pop_h5_path = os.path.join(tmpdir, "zero_pop.h5")

            with h5py.File(zero_pop_h5_path, "w") as h5file:
                status_group = h5file.create_group("status_summary")
                dt = [('timestep', 'i4'), ('S', 'i4'), ('I', 'i4')]
                data = [(0, 10, 5)]
                status_group.create_dataset("summary", data=data, dtype=dt)

                # Zero population config -> corrupt simulation!
                config_group = h5file.create_group("config")
                sim_config = {"population": 0}
                config_group.create_dataset(
                    "simulation_config",
                    data=json.dumps(sim_config).encode("utf-8")
                )

            with pytest.raises(ValueError, match="Total population in configurations is zero"):
                plot_status_summary_from_hdf5(zero_pop_h5_path)

    @pytest.mark.parametrize("model_key", ["seir", "seisir", "seiqrdv"])
    def test_plot_status_summary_has_data(self, model_key):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simulation output
            town_params = TownParameters(num_pop=50, num_init_spreader=5)
            folk_class = MODEL_MATRIX[model_key][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                model_key, town_params, step_events=step_events, timesteps=10, seed=True)

            h5_path = os.path.join(tmpdir, "test_plot.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            # Capture the current figure instead of just mocking show
            with patch('matplotlib.pyplot.show'):
                plot_status_summary_from_hdf5(h5_path)

                # Get the current figure
                fig = plt.gcf()
                axes = fig.get_axes()

                # Verify figure has content
                assert len(axes) > 0, "Plot should have at least one axis"

                # Check that axes have data
                for ax in axes:
                    lines = ax.get_lines()
                    assert len(
                        lines) > 0, f"Axis should have at least one line plot"

                    # Check that lines actually have data points
                    for line in lines:
                        xdata, ydata = line.get_data()
                        assert len(xdata) > 0, "Line should have x-data"
                        assert len(ydata) > 0, "Line should have y-data"

                # Verify labels exist
                assert fig.get_suptitle() or any(ax.get_title()
                                                 for ax in axes), "Plot should have a title"

                plt.close(fig)  # Clean up


class TestValidateAndMergeColormap:

    @pytest.mark.parametrize("default_map,user_map,valid_keys,parameter_name,expected_missing", [
        # Test case: Default map missing colors for valid keys
        ({"type1": "#FF0000", "type2": "#00FF00"}, None,
         ["type1", "type2", "type3", "type4"], "test param", ["type3", "type4"]),

        # Test case: Even after merging user map, there are still some missing
        # colors
        ({"type1": "#FF0000"}, {"type2": "#00FF00"},
         ["type1", "type2", "type3"], "test param", ["type3"]),

        # Test case: User map provided but doesn't cover all missing
        ({"x": "#FF0000"}, {"y": "#00FF00", "z": "#0000FF"},
         ["x", "y", "z", "w", "v"], "category", ["v", "w"]),
    ])
    def test_missing_colors_raises_value_error(
            self,
            default_map,
            user_map,
            valid_keys,
            parameter_name,
            expected_missing):
        from simcronomicon.visualization.visualization_util import _validate_and_merge_colormap

        # Sort expected missing colors to match function behavior
        expected_missing_sorted = sorted(expected_missing)
        expected_error_pattern = rf"Missing colors for valid {parameter_name}\(s\): {
            ', '.join(expected_missing_sorted)}"

        with pytest.raises(ValueError, match=expected_error_pattern):
            _validate_and_merge_colormap(
                default_map, user_map, valid_keys, parameter_name)

    @pytest.mark.parametrize("default_map,user_map,valid_keys,parameter_name,expected_result", [
        # All these test cases shouldn't produce any error
        # Test case: All valid keys have colors.
        ({"type1": "#FF0000", "type2": "#00FF00"}, {"type3": "#0000FF"},
         ["type1", "type2", "type3"], "test param",
         {"type1": "#FF0000", "type2": "#00FF00", "type3": "#0000FF"}),

        # Test case: User map overrides defaults
        ({"type1": "#FF0000", "type2": "#00FF00"}, {"type1": "#FFFFFF"},
         ["type1", "type2"], "test param",
         {"type1": "#FFFFFF", "type2": "#00FF00"}),

        # Test case: Only defaults, all covered
        ({"a": "#FF0000", "b": "#00FF00"}, None,
         ["a", "b"], "status",
         {"a": "#FF0000", "b": "#00FF00"}),

        # Test case: Only user map, all covered
        ({}, {"x": "#FF0000", "y": "#00FF00"},
         ["x", "y"], "category",
         {"x": "#FF0000", "y": "#00FF00"}),

        # Test case: Complex merge with overrides
        ({"a": "#FF0000", "b": "#00FF00", "c": "#0000FF"}, {"b": "#FFFFFF", "d": "#FFFF00"},
         ["a", "b", "c", "d"], "type",
         {"a": "#FF0000", "b": "#FFFFFF", "c": "#0000FF", "d": "#FFFF00"}),
    ])
    def test_successful_color_mapping(
            self,
            default_map,
            user_map,
            valid_keys,
            parameter_name,
            expected_result):
        from simcronomicon.visualization.visualization_util import _validate_and_merge_colormap

        # Should not raise an error
        result = _validate_and_merge_colormap(
            default_map, user_map, valid_keys, parameter_name)
        assert result == expected_result

    @pytest.mark.parametrize("default_map,user_map,valid_keys,parameter_name,expected_warnings", [
        # Test case: User provides invalid key
        ({"type1": "#FF0000"}, {"invalid_key": "#00FF00", "type1": "#FFFFFF"},
         ["type1"], "test param",
         ["Warning: 'invalid_key' is not a valid test param"]),

        # Test case: Invalid color format
        ({"type1": "#FF0000"}, {"type1": "not_a_color"},
         ["type1"], "test param",
         ["Warning: 'not_a_color' for type1 is not a valid hex color"]),

        # Test case: Both invalid key and invalid color
        ({"type1": "#FF0000"}, {"invalid_key": "bad_color", "type1": "#FFFFFF"},
         ["type1"], "test param",
         ["Warning: 'invalid_key' is not a valid test param",
          "Warning: 'bad_color' for invalid_key is not a valid hex color"]),
    ])
    def test_warnings_for_invalid_inputs(
            self,
            default_map,
            user_map,
            valid_keys,
            parameter_name,
            expected_warnings):
        from simcronomicon.visualization.visualization_util import _validate_and_merge_colormap

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # This should generate warnings but not raise an error (if all
            # valid keys are covered)
            try:
                _validate_and_merge_colormap(
                    default_map, user_map, valid_keys, parameter_name)
            except ValueError:
                pass  # Ignore ValueError for this test, we're only testing warnings

            # Check that expected warnings were issued
            warning_messages = [str(warning.message) for warning in w]

            for expected_warning in expected_warnings:
                assert any(expected_warning in msg for msg in warning_messages), \
                    f"Expected warning '{expected_warning}' not found in {warning_messages}"


class TestVisualizeMap:
    def test_set_plotly_renderer_no_ipython_nameerror(self):
        from simcronomicon.visualization.visualization_util import _set_plotly_renderer
        import plotly.io as pio

        # Store original renderer to restore later
        original_renderer = pio.renderers.default

        try:
            # Import the function first to make the patch target clear
            from simcronomicon.visualization.visualization_util import _set_plotly_renderer

            # Mock NameError when get_ipython is not available
            with patch('simcronomicon.visualization.visualization_util.get_ipython', side_effect=NameError("name 'get_ipython' is not defined")):
                _set_plotly_renderer()
                # Should set browser renderer when not in IPython
                assert pio.renderers.default == "browser"
        finally:
            # Restore original renderer
            pio.renderers.default = original_renderer

    @pytest.mark.parametrize("shell_name,expected_renderer", [
        ('ZMQInteractiveShell', 'notebook'),      # Jupyter notebook
        ('TerminalInteractiveShell', 'browser'),   # IPython terminal
        ('google.colab._shell', 'browser'),        # Google Colab
        ('SpyderShell', 'browser'),                # Spyder IDE
    ])
    def test_set_plotly_renderer_different_shells(
            self, shell_name, expected_renderer):
        from simcronomicon.visualization.visualization_util import _set_plotly_renderer
        import plotly.io as pio

        # Mock different IPython shell environments
        mock_ipython = MagicMock()
        mock_ipython.__class__.__name__ = shell_name

        # Store original renderer
        original_renderer = pio.renderers.default

        try:
            # Patch get_ipython in the correct module where
            # _set_plotly_renderer is defined
            with patch('simcronomicon.visualization.visualization_util.get_ipython', return_value=mock_ipython):
                _set_plotly_renderer()
                assert pio.renderers.default == expected_renderer
        finally:
            # Restore original renderer
            pio.renderers.default = original_renderer

    def test_plot_place_types_scatter(self):
        graphml_path, config_path, town = create_test_town_files()

        try:
            # Mock plotly show to prevent actual display
            with patch('plotly.graph_objects.Figure.show') as mock_show:
                plot_scatter.plot_place_types_scatter(
                    graphml_path, config_path)
                mock_show.assert_called_once()
        finally:
            # Cleanup
            for file_path in [graphml_path, config_path]:
                if os.path.exists(file_path):
                    os.remove(file_path)

    def test_visualize_place_types_invalid_file_extensions(self):
        with pytest.raises(AssertionError, match="Expected a .graphmlz file"):
            plot_scatter.plot_place_types_scatter(
                "wrong.txt", "config.json")

        with pytest.raises(AssertionError, match="Expected a .json file"):
            plot_scatter.plot_place_types_scatter(
                "graph.graphmlz", "wrong.txt")

    def test_plot_agents_scatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simulation output
            town_params = TownParameters(num_pop=20, num_init_spreader=2)
            folk_class = MODEL_MATRIX["seir"][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                "seir", town_params, step_events=step_events, timesteps=3, seed=True)

            h5_path = os.path.join(tmpdir, "test_folks.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            graphml_path, config_path, _ = create_test_town_files()

            try:
                # Mock plotly show to prevent actual display
                with patch('plotly.graph_objects.Figure.show') as mock_show:
                    plot_scatter.plot_agents_scatter(
                        h5_path, graphml_path)
                    mock_show.assert_called_once()
            finally:
                # Cleanup
                for file_path in [graphml_path, config_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)

    def test_visualize_folks_invalid_file_extensions(self):
        with pytest.raises(AssertionError, match="Expected a .h5 file"):
            plot_scatter.plot_agents_scatter(
                "wrong.txt", "graph.graphmlz")

        with pytest.raises(AssertionError, match="Expected a .graphmlz file"):
            plot_scatter.plot_agents_scatter("sim.h5", "wrong.txt")

    @pytest.mark.parametrize("time_interval,should_pass,expected_error", [
        ((0, 2), True, None),
        ((1, 3), True, None),
        ([-1, 2], False, AssertionError),  # Negative start
        ((0, -1), False, AssertionError),  # Negative end
        ((2, 1), False, AssertionError),   # Start > end
        ("invalid", False, AssertionError),  # Wrong type
        ((0, 1, 2), False, AssertionError),  # Too many values
    ])
    def test_visualize_folks_time_interval_validation(
            self, time_interval, should_pass, expected_error):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simulation output
            town_params = TownParameters(num_pop=10, num_init_spreader=1)
            folk_class = MODEL_MATRIX["seir"][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                "seir", town_params, step_events=step_events, timesteps=5, seed=True)

            h5_path = os.path.join(tmpdir, "test_time_interval.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            graphml_path, config_path, _ = create_test_town_files()

            try:
                if should_pass:
                    with patch('plotly.graph_objects.Figure.show') as mock_show:
                        plot_scatter.plot_agents_scatter(
                            h5_path, graphml_path, time_interval=time_interval
                        )
                        mock_show.assert_called_once()
                else:
                    with pytest.raises(expected_error):
                        plot_scatter.plot_agents_scatter(
                            h5_path, graphml_path, time_interval=time_interval
                        )
            finally:
                # Cleanup
                for file_path in [graphml_path, config_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)

    def test_visualize_folks_time_interval_exceeds_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simulation with only 3 timesteps
            town_params = TownParameters(num_pop=10, num_init_spreader=1)
            folk_class = MODEL_MATRIX["seir"][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                "seir", town_params, step_events=step_events, timesteps=3, seed=True)

            h5_path = os.path.join(tmpdir, "test_exceed.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            graphml_path, config_path, _ = create_test_town_files()

            try:
                with patch('plotly.graph_objects.Figure.show') as mock_show:
                    # Request timesteps beyond what's available
                    import warnings
                    with warnings.catch_warnings(record=True) as w:
                        warnings.simplefilter("always")
                        plot_scatter.plot_agents_scatter(
                            h5_path, graphml_path, time_interval=(0, 10)
                        )

                        # Check that warning was there
                        assert len(w) == 1
                        assert "exceeds maximum timestep" in str(w[0].message)

                    mock_show.assert_called_once()
            finally:
                # Cleanup
                for file_path in [graphml_path, config_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)

    def test_visualize_folks_no_data_in_interval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simulation output
            town_params = TownParameters(num_pop=10, num_init_spreader=1)
            folk_class = MODEL_MATRIX["seir"][2]
            step_events = default_test_step_events(folk_class)
            sim, _, _ = setup_simulation(
                "seir", town_params, step_events=step_events, timesteps=3, seed=True)

            h5_path = os.path.join(tmpdir, "test_no_data.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            graphml_path, config_path, _ = create_test_town_files()

            try:
                # Request time interval with start > max timestep should raise
                # ValueError
                with pytest.raises(ValueError, match="Start timestep .* is greater than maximum available timestep"):
                    plot_scatter.plot_agents_scatter(
                        h5_path, graphml_path, time_interval=(100, 200)
                    )
            finally:
                # Cleanup
                for file_path in [graphml_path, config_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)


class TestVisualizationUtilities:

    def test_visualize_folks_has_data_flexible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simulation and town data
            town_params = TownParameters(num_pop=20, num_init_spreader=2)
            folk_class = MODEL_MATRIX["seir"][2]
            step_events = default_test_step_events(folk_class)
            sim, town, _ = setup_simulation(
                "seir", town_params, step_events=step_events, timesteps=3, seed=True)

            h5_path = os.path.join(tmpdir, "test_folks.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            graphml_path, config_path, _ = create_test_town_files()

            try:
                captured_fig = None

                def capture_figure(self):
                    nonlocal captured_fig
                    captured_fig = self

                with patch.object(go.Figure, 'show', capture_figure):
                    plot_scatter.plot_agents_scatter(
                        h5_path, graphml_path)

                # Verify the figure has data
                assert captured_fig is not None, "Figure should be created"
                assert len(
                    captured_fig.data) > 0, "Figure should have data traces"

                # Look for any traces with coordinate data
                coordinate_traces = []
                for trace in captured_fig.data:
                    has_coords = False

                    # Check for different coordinate systems
                    if hasattr(trace, 'lon') and hasattr(trace, 'lat'):
                        if (trace.lon is not None and trace.lat is not None and
                                len(trace.lon) > 0 and len(trace.lat) > 0):
                            has_coords = True
                    elif hasattr(trace, 'x') and hasattr(trace, 'y'):
                        if (trace.x is not None and trace.y is not None and
                                len(trace.x) > 0 and len(trace.y) > 0):
                            has_coords = True

                    if has_coords:
                        coordinate_traces.append(trace)

                assert len(coordinate_traces) > 0, \
                    f"Should have traces with coordinate data. Found {len(captured_fig.data)} traces of types: " \
                    f"{[trace.type for trace in captured_fig.data]}"

                # Verify the figure has a layout
                assert hasattr(
                    captured_fig, 'layout'), "Figure should have layout"

            finally:
                # Cleanup
                for file_path in [graphml_path, config_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
