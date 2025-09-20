import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

import streamlit as st


def build_scenario_df(tests):
    rows = []
    for idx, test in enumerate(tests, start=1):
        for scenario in test["scenarios"]:
            rows.append({
                "test_index": idx,
                "test_id": test["id"],
                "scenario": scenario
            })
    return pd.DataFrame(rows)

def plot_scenario_heatmaps(tests, title, cell_size=10, fig_height=600):

    grid_df, _ = make_presence_df(
        tests, 
        flipped=False
    )

    grid_df = grid_df.astype(int)
    # Ensure tidy ordering (optional but often handy)
    grid_df.index = [f"S{i}" for i in grid_df.index.to_list()]                                # rows S_x
    grid_df.columns = [f"T{j}" for j in grid_df.columns.to_list()]                      # cols T_x
    n_rows, n_cols = grid_df.shape

    fig = go.Figure(
        go.Scatter(

            x=np.tile(np.arange(n_cols), n_rows),
            y=np.repeat(np.arange(n_rows), n_cols), 
            mode='markers'
        )
    )
    fig.update_traces(
        marker_symbol='square', 
        marker_size=cell_size, 
        marker_color=grid_df.to_numpy().flatten(),
        marker_cmin=0, marker_cmax=1, 
        marker_colorscale=[[0, "white"],
                        [1, "steelblue"]],
        marker_line_color='black', 
        marker_line_width=1
    )
    fig.update_xaxes(
        title="Test Configuration",
        range=[-2, n_cols-1],  # to center the labels
        tickmode="array",
        tickvals=np.arange(n_cols),
        ticktext=grid_df.columns,
        mirror=True,                
        tickangle=-90,
        side="top",
        showgrid=True,             # borders come from the markers
        tick0=0,
        dtick=1,
        # automargin=False,
        tickfont=dict(size=8.5, color="black"),
        tickson="boundaries",
    )
    
    fig.update_yaxes(
        title="Scenario ID",
        range=[-0.5, n_rows - 0.5],  # to center the labels
        autorange="reversed",       # S1 at the top
        tickmode="array",
        tickvals=np.arange(n_rows),
        ticktext=grid_df.index,
        mirror=True,
        showgrid=True,
        dtick=1,
        tick0=0,
        tickson="boundaries",
        # automargin=False,
    )
    
    fig.update_layout(
        title=title,
        height=fig_height, 
        # margin=dict(l=0, r=0, t=0, b=BOTTOM),
        # plot_bgcolor="white", 
    )

    return fig

def plot_sequence_dots(tests, title, cell_size=10, fig_height=600):
    
    # Extract ordered test IDs and their scenarios from tests
    # test: [{id: "1", scenarios: ["3", "19"]}, {id: "2", scenarios: ["3", "19", "5"]}, ...]
    # extract test id and the consequent scenario in separate lists
    seq_ids = []
    test_ids = []
    for test in tests:
        test_ids.extend([test['id']] * len(test['scenarios']))
        seq_ids.extend(test['scenarios'])

    fig = go.Figure(go.Scatter(
        x=test_ids,
        y=seq_ids,
        mode='markers',
        marker=dict(size=cell_size),
    ))
    fig.update_layout(
        title=title,
        xaxis_title='Test ID (in execution order)',
        yaxis_title='Scenario ID',
        xaxis=dict(
            type='category', 
            categoryorder='array', 
            range=[-0.5, len(tests)],  # to center the labels
            categoryarray=test_ids, 
            showgrid=True,
            dtick=1,
            tick0=0,
            tickson='boundaries',
            tickangle=-90,
            tickfont=dict(size=8.5, color='black'),
            mirror="allticks",
        ),
        yaxis=dict(
            type='category', 
            categoryorder='array', 
            range=[-0.5, len(seq_ids)-0.5],  # to center the labels
            categoryarray=sorted(seq_ids), 
            autorange='reversed',
            showgrid=True,
            dtick=1,
            tick0=0,
            tickson='boundaries',
            mirror="allticks",
        ),
        showlegend=False,
        height=fig_height,
    )

    return fig

def build_scenario_timeline(tests, title, cell_size=10, fig_height=600):
    """
    Build a Plotly timeline (Gantt) figure that shows how long each scenario
    remains active across a test sequence.

    Parameters
    ----------
    tests : list[dict]
        The list of test dictionaries loaded from the JSON file:
        [
          {
            "id": "1",
            "scenarios": ["3", "19"],
            "apply":   ["3", "19"],
            "retract": []
          },
          ...
        ]
    title : str
        Figure title.

    Returns
    -------
    plotly.graph_objects.Figure
    """

    ordered_test_ids = [str(t["id"]) for t in tests]        # X‑axis order
    scenario_ids = sorted({s for t in tests for s in t["scenarios"]})
    ordered_scenario_ids = list(map(str, scenario_ids))     # Y‑axis order

    # ------------------------------------------------------------------
    # 2. Flatten (test ID, scenario ID) pairs for scatter plotting  -----
    # ------------------------------------------------------------------
    xs, ys = [], []
    for t in tests:
        x = str(t["id"])
        for s in t["scenarios"]:
            xs.append(x)
            ys.append(str(s))

    # ------------------------------------------------------------------
    # 3. Build the figure  ---------------------------------------------
    # ------------------------------------------------------------------
    fig = go.Figure(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            marker=dict(size=cell_size, symbol="square"),   # “small bar” feel
            hovertemplate="Test ID: %{x}<br>Scenario ID: %{y}<extra></extra>",
        )
    )

    # 4. Cosmetics: preserve categorical order exactly as requested
    fig.update_layout(
        title=title,
        xaxis=dict(
            title="Test ID (in execution order)",
            type="category",
            categoryorder="array",
            range=[-0.5, len(ordered_test_ids) - 0.5],  # to center the labels
            categoryarray=ordered_test_ids,
            tickangle=-90,
            tickfont=dict(size=8.5, color="black"),
            tickson="boundaries",
            showgrid=True,
            dtick=1,
            tick0=0,
            mirror="allticks",
        ),
        yaxis=dict(
            title="Scenario ID",
            type="category",
            categoryorder="array",
            # reverse so the numerically first scenario appears at the top
            categoryarray=ordered_scenario_ids[::-1],
            showgrid=True,
            dtick=1,
            tick0=0,
            tickson="boundaries",
            mirror="allticks",
        ),
        height=fig_height,
        margin=dict(l=80, r=40, t=80, b=120)
    )
    return fig


# ----------------------------------------------------------------------
# 1. Build Scenario × Test matrix with status codes
# ----------------------------------------------------------------------
def make_presence_df(tests, flipped=False) -> pd.DataFrame:
    """
    Return a DataFrame whose values are:
        2 → newly applied
        1 → active (carried over)
       -1 → retracted
        0 → inactive
    """

    test_ids      = [str(t["id"]) for t in tests]           # column order
    scenario_all  = sorted({s for t in tests for s in t["scenarios"]}
                           | {s for t in tests for s in t["apply"]}
                           | {s for t in tests for s in t["retract"]})
    df = pd.DataFrame(0, index=scenario_all, columns=test_ids, dtype=int)

    for t in tests:
        tid = str(t["id"])

        # 2 → newly applied
        for sc in t["apply"]:
            df.at[sc, tid] = 2

        # 1 → active but not newly applied
        for sc in t["scenarios"]:
            if df.at[sc, tid] == 0:               # skip if already marked 2
                df.at[sc, tid] = 1

        # -1 → retracted
        for sc in t["retract"]:
            df.at[sc, tid] = -1                  # overwrite any 0

    df.index.name   = "Scenario ID"
    df.columns.name = "Test ID"

    if flipped:
        # Transpose the DataFrame to have tests as rows and scenarios as columns
        df = df.T

    return df, 1


# ----------------------------------------------------------------------
# 2. Style function with custom colours
# ----------------------------------------------------------------------
def style_presence(df: pd.DataFrame, show_additional: bool = False):
    colours = {2: "#4f8aff",     # light blue  – newly applied
               1: "#2a4b8d",     # dark  blue  – active / carried‑over
              -1: "#ffafaf",     # light red   – retracted
               0: "#ffffff"}     # white       – inactive

    if not show_additional:
        colours.update({
            0: "#ffffff", 
            1: "#2a4b8d",
            -1: '#2a4b8d',
            2: '#2a4b8d'
        })

    

    # formatting hides the numeric values
    return df.style.applymap(lambda v: f"background-color: {colours[v]}")\
                    .format("") \
                    .set_table_styles([
                        {"selector": "tr", "props": "line-height: 1px;"},
                        {"selector": "td,th", "props": "line-height: inherit; padding: 0;"}
                    ])

def make_cost_plots(tests, costs_data, title="", type="absolute", show_cumsum=True, display_in_execorder=True,
                    barcolor="skyblue", linecolor="red", fig_height=600):
    """
    Create a bar plot of the total costs per test.
    There are four types of cost plots as follows:
        - Isolated Test Costs[key="absolute"]: Costs per test config, if they are applied from scratch.
            - Modes: 1. "in order of execution" or 2. "in order of cost (least to most expensive)"
        - Unoptimized Ordered Test Costs[key="relative"]: Costs per test config, if they are applied+retracted in the order of execution.
            - Modes: 1. single y-axis: Application cost on y-axis on left or 2. double y-axis: Application cost on left, cumulative cost on right
        - Optimized Ordered Test Costs[key="relative"]: Costs per test config, if they are applied+retracted in the order of execution.
            - Modes: 1. single y-axis: Application cost on y-axis on left or 2. double y-axis: Application cost on left, cumulative cost on right
    """
    
    # Lookup table for scenario costs Scenario ID → cost
    costs_lookup = costs_data.get("scenarios", {})
    # costs_lookup = {
    #         int(b["scenarioID"]["value"]): int(b["cost"]["value"])
    #         for b in raw["results"]["bindings"]
    #     }
    
    # st.write(costs_lookup)

    # Build a DataFrame with test IDs and their costs
    test_costs = []
    for i,test in enumerate(tests):
        test_id = test["id"]
        total_cost = sum(costs_lookup.get(scenario, 0) for scenario in test["scenarios"])
        test_costs.append({"test_id": test_id, "absolute_total_cost": total_cost})
    
    costs_df = pd.DataFrame(test_costs)
    # costs_df["test_id"] = costs_df["test_id"].astype(str) 


    # Add the column for ordered cost
    for i, row in costs_df.iterrows():
        test_id = row["test_id"]
        test = [test for test in tests if test["id"] == test_id][0]
        apply_test_ids = test.get("apply", [])
        retract_test_ids = test.get("retract", [])
        costs_df.at[i, "scenarios"] = ", ".join([str(s) for s in test.get("scenarios", [])])
        costs_df.at[i, "apply"] = ", ".join([str(s) for s in apply_test_ids])
        costs_df.at[i, "retract"] = ", ".join([str(s) for s in retract_test_ids])
        ordered_cost = sum(costs_lookup.get(scenario, 0) for scenario in apply_test_ids+ retract_test_ids)
        costs_df.at[i, "total_ordered_cost"] = ordered_cost   
        
    # Add column for culmulative cost for the excution order
    costs_df["cumulative_cost"] = costs_df["total_ordered_cost"].cumsum()
    # for the last entry in cost_df, add the valur of absolute_total_cost to cumulative_cost to match the Combine dcost in metrics
    # this value is the cost to finally retract the last test configuration
    costs_df.at[len(costs_df)-1, "cumulative_cost"] = costs_df.at[len(costs_df)-1, "cumulative_cost"] + costs_df.at[len(costs_df)-1, "absolute_total_cost"]

    subtitle=""
    cost_column = "absolute_total_cost"
    yaxis_tag = "(in execution order of the test configuration)"
    if type=="absolute":
        subtitle = "Absolute cost calculated for each test configration in isolation (absolute cost of each test configuration)"
        cost_column = "absolute_total_cost"
    elif type=="relative":
        subtitle = "Running cost calculated for test configuration based on application and retraction cost"
        cost_column = "total_ordered_cost"
    if not display_in_execorder:
        costs_df = costs_df.sort_values(by=[cost_column])
        yaxis_tag = "(least to most expensive configuration)"


    # st.write(costs_df)
    
    # st.write(costs_df.sort_values(by=[cost_column])[cost_column].cumsum().reset_index(drop=True))
    
    # Z-ORDERING: https://community.plotly.com/t/change-traces-order/84830/5
    bar_trace = go.Bar(
            x=costs_df["test_id"], 
            y=costs_df[cost_column],
            name="Test Configuration Cost",
            marker=dict(color=barcolor), 
            zorder=1,
        )
    line_trace = go.Line(
            x=costs_df["test_id"], 
            # y=costs_df[cost_column].cumsum(),
            y=costs_df["cumulative_cost"],
            name="Cumulative Cost",
            line=dict(color=linecolor, width=1,),
            zorder=0,
        )

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(bar_trace, secondary_y=False)

    if show_cumsum:
        fig.add_trace(line_trace, secondary_y=True)

    fig.update_layout(
        title=title + f"<br><sup>{subtitle}</sup>",
        xaxis_title="Test ID " + yaxis_tag,
        yaxis_title="Total Cost",
        xaxis=dict(
            type='category',
            categoryorder='array',
            categoryarray=costs_df["test_id"].tolist(),
            tickangle=-90,
            tickfont=dict(size=8.5, color='black'),
            # tickson='boundaries',
            # showgrid=True,
            dtick=1,
            # tick0=0,
            # mirror="allticks",
        ),
        # yaxis=dict(
        #     type="category",
        #     categoryorder='array',
        #     categoryarray=costs_df.sort_values(by=[cost_column])[cost_column].cumsum().to_list()
        # ),
        yaxis2=dict(                     # secondary y-axis
            title="Cumulative Costs",    # axis title
            titlefont=dict(color="red"), # title color
            tickfont=dict(color="red"),  # tick labels color
            tickprefix="$",            # tick prefix
        ),
        height=fig_height,
        showlegend=True,
        legend=dict(
            xanchor="right",
            yanchor="top",
            x=0.99, y=1.02,
            orientation='h'
        )
    )

    return fig

def make_cost_histogram(unopt_tests, opt_tests, costs_data, title="", 
                        nbins=150, bargap=0.1, fig_height=600):
    """
    Create a bar plot of the total costs per test.
    There are four types of cost plots as follows:
        - Isolated Test Costs[key="absolute"]: Costs per test config, if they are applied from scratch.
            - Modes: 1. "in order of execution" or 2. "in order of cost (least to most expensive)"
        - Unoptimized Ordered Test Costs[key="relative"]: Costs per test config, if they are applied+retracted in the order of execution.
            - Modes: 1. single y-axis: Application cost on y-axis on left or 2. double y-axis: Application cost on left, cumulative cost on right
        - Optimized Ordered Test Costs[key="relative"]: Costs per test config, if they are applied+retracted in the order of execution.
            - Modes: 1. single y-axis: Application cost on y-axis on left or 2. double y-axis: Application cost on left, cumulative cost on right
    """
    
    # Lookup table for scenario costs Scenario ID → cost
    costs_lookup = costs_data.get("scenarios", {})
    # costs_lookup = {
    #         int(b["scenarioID"]["value"]): int(b["cost"]["value"])
    #         for b in raw["results"]["bindings"]
    #     }
    
    # st.write(costs_lookup)

    # Build a DataFrame with test IDs and their costs
    test_costs = []
    for i,test in enumerate(unopt_tests):
        test_id = test["id"]
        total_cost = sum(costs_lookup.get(scenario, 0) for scenario in test["scenarios"])
        test_costs.append({"test_id": test_id, "absolute_total_cost": total_cost})
    
    unopt_costs_df = pd.DataFrame(test_costs)
    unopt_costs_df["type"] = "Unoptimized Test Cost"
    # costs_df["test_id"] = costs_df["test_id"].astype(str) 


    # Add the column for ordered cost
    for i, row in unopt_costs_df.iterrows():
        test_id = row["test_id"]
        test = [test for test in unopt_tests if test["id"] == test_id][0]
        apply_test_ids = test.get("apply", [])
        retract_test_ids = test.get("retract", [])
        unopt_costs_df.at[i, "scenarios"] = ", ".join([str(s) for s in test.get("scenarios", [])])
        unopt_costs_df.at[i, "apply"] = ", ".join([str(s) for s in apply_test_ids])
        unopt_costs_df.at[i, "retract"] = ", ".join([str(s) for s in retract_test_ids])
        ordered_cost = sum(costs_lookup.get(scenario, 0) for scenario in apply_test_ids+ retract_test_ids)
        unopt_costs_df.at[i, "total_ordered_cost"] = ordered_cost   
        
    # Add column for culmulative cost for the excution order
    unopt_costs_df["cumulative_cost"] = unopt_costs_df["total_ordered_cost"].cumsum()
    
    test_costs = []
    for i,test in enumerate(opt_tests):
        test_id = test["id"]
        total_cost = sum(costs_lookup.get(scenario, 0) for scenario in test["scenarios"])
        test_costs.append({"test_id": test_id, "absolute_total_cost": total_cost})
    
    opt_costs_df = pd.DataFrame(test_costs)
    opt_costs_df["type"] = "Optimized Test Cost"
    # costs_df["test_id"] = costs_df["test_id"].astype(str) 


    # Add the column for ordered cost
    for i, row in opt_costs_df.iterrows():
        test_id = row["test_id"]
        test = [test for test in opt_tests if test["id"] == test_id][0]
        apply_test_ids = test.get("apply", [])
        retract_test_ids = test.get("retract", [])
        opt_costs_df.at[i, "scenarios"] = ", ".join([str(s) for s in test.get("scenarios", [])])
        opt_costs_df.at[i, "apply"] = ", ".join([str(s) for s in apply_test_ids])
        opt_costs_df.at[i, "retract"] = ", ".join([str(s) for s in retract_test_ids])
        ordered_cost = sum(costs_lookup.get(scenario, 0) for scenario in apply_test_ids+ retract_test_ids)
        opt_costs_df.at[i, "total_ordered_cost"] = ordered_cost   
        
    # Add column for culmulative cost for the excution order
    opt_costs_df["cumulative_cost"] = opt_costs_df["total_ordered_cost"]#.cumsum()

    costs_df = pd.concat([opt_costs_df, unopt_costs_df], ignore_index=True)

    # st.write(costs_df)

    # plot a histogram for total_ordered_cost column colored by the type column
    fig = px.histogram(
        costs_df, 
        x="total_ordered_cost", 
        nbins=nbins,
        color="type",
        # get two distinc colors for the bars: red and blue
        color_discrete_map={
            "Optimized Test Cost": "red",
            "Unoptimized Test Cost": "blue",
        }, 
        barmode="overlay",
        title=title,
        labels={"total_ordered_cost": "Total Cost in order of execution (with application and retraction)"},
        height=fig_height,
    )
    # rename the y-axis to "Number of Test Configurations"
    # rename legend title to "Test Cost Type"
    # add "$" to the x-axis ticks and change the step gap to 5
    # add gridlines to the x-axis
    # change the z-axis order so that unoptimized bars are ahead of optimized bars
    fig.update_layout(
        yaxis_title="Number of Test Configurations",
        legend_title="Test Cost Type",
        xaxis=dict(
            tickprefix="$",
            dtick=5,
            showgrid=True,
        ),
        bargap=bargap,
        bargroupgap=0.5,
        legend=dict(
            title="Test Cost Type",
            xanchor="right",
            yanchor="top",
            x=0.99, y=0.99,
            orientation='h'
        )
    )

    return fig
    

def build_sankey(
    scenarios_df: pd.DataFrame,
    reqs_df: pd.DataFrame,
    selected_scenarios: list[int],
    plot_height: int,
) -> go.Figure:
    """
    Build a Scenario → Requirement → Quantity Sankey focused on the user
    selection.
    """
    # ------------------------------------------------------------------ nodes
    #   1. keep only rows for the chosen scenario(s)
    s_df = scenarios_df.query("scenarioID in @selected_scenarios")


    # st.write(s_df)
    list_of_requirements = [i.strip() for x in s_df["requirementIDs"].to_list() for i in x.split(",")]
    # st.write(list_of_requirements)
    r_df = reqs_df.query("id in @list_of_requirements")
    # st.write(r_df)


    #    2. build sr_df with scenrioID, requirementIDs, quantity  
    # s_df -> dataframe with scenarioID, requirementIDs (comma separated)
    # r_df -> dataframe with requirementID, quantity
    # Join scenario with requirements and quantities
    # sr_df = selected scenario -> requirements -> quantities
    sr_df = (
        s_df.assign(
            requirementIDs=lambda d: d["requirementIDs"].str.split(",").apply(lambda x: [i.strip() for i in x])
        )  
        .explode("requirementIDs")
        .merge(
            r_df[["id", "quantity"]],
            left_on="requirementIDs",
            right_on="id",
            how="left",
        )
        .rename(columns={"scenarioID": "scenario_id", "id": "requirement_id", "quantity": "quantity_id"})
    ).drop(columns=["requirementIDs"])
    # st.write(sr_df)
    
    #   3. build the sankey nodes
    # labels_s = [f"S{sid}" for sid in s_df["scenarioID"].unique()]
    # labels_r = [f"R{rid}" for rid in sr_df["requirement_id"].unique()]
    # labels_q = [f"Q{qid}" for qid in sr_df["quantity_id"].unique()]
    labels_s = [f"{sid}" for sid in s_df["scenarioID"].unique()]
    labels_r = [f"{rid}" for rid in sr_df["requirement_id"].unique()]
    labels_q = [f"{qid}" for qid in sr_df["quantity_id"].unique()]
    labels   = labels_s + labels_r + labels_q
    index    = {lab: i for i, lab in enumerate(labels)}
    # st.write(labels)
    # ------------------------------------------------------------------ links
    # Scenario ▶ Requirement
    l1 = (
        sr_df[["scenario_id", "requirement_id"]]
        .drop_duplicates()
        .assign(
            # source=lambda d: d["scenario_id"].map(lambda x: index[f"S{x}"]),
            # target=lambda d: d["requirement_id"].map(lambda x: index[f"R{x}"]),
            source=lambda d: d["scenario_id"].map(lambda x: index[f"{x}"]),
            target=lambda d: d["requirement_id"].map(lambda x: index[f"{x}"]),
            value=1,
        )
    )
    # Requirement ▶ Quantity
    l2 = (
        sr_df[["requirement_id", "quantity_id"]]
        .drop_duplicates()
        .assign(
            source=lambda d: d["requirement_id"].map(lambda x: index[f"{x}"]),
            target=lambda d: d["quantity_id"].map(lambda x: index[f"{x}"]),
            value=1,
        )
    )
    links = pd.concat([l1, l2], ignore_index=True)
    # st.write(links)
    # ------------------------------------------------------------------ plotly
    sankey = go.Sankey(
        arrangement="snap",
        node=dict(
            label=labels, 
            pad=5,
            thickness=100,
            line=dict(color="black", width=0.5),
                  ),
        link=dict(
            source=links["source"],
            target=links["target"],
            value=links["value"],
            color="rgba(0, 0, 0, 0.1)",
            
        ),
        # adjust the color and boldness of text labels
        textfont=dict(
            color="black",
            size=9,
            family="Arial, sans-serif",
        ),
        # textposition="inside",
        
    )   
    return go.Figure(data=[sankey]).update_layout(
        title="Scenario → Requirement → Quantity connections",
        height=plot_height,
    )