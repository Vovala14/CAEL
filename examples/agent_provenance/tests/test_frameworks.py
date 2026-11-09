import copy
import json

import pytest
from cases import CASES

from cael_provenance import ProvenanceError, verify


@pytest.mark.parametrize(
    "name,inputs,observed,intended", CASES, ids=[c[0] for c in CASES]
)
def test_actual_langgraph_workflow(
    runtime, artifact_dir, name, inputs, observed, intended
):
    from cael_provenance.langgraph import graph_builder

    result = graph_builder(runtime).compile().invoke({"request": inputs})
    assert result["certificate"] == runtime.answer(inputs)
    assert result["verified"] is (observed != "unsupported")
    (artifact_dir / ("langgraph-" + name + ".json")).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )


def test_real_toolnode_preserves_full_artifact(runtime):
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode

    from cael_provenance.langgraph import proof_tool

    inputs = CASES[3][1]
    node = ToolNode([proof_tool(runtime)])
    builder = StateGraph(MessagesState)
    builder.add_node("tools", node)
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    response = builder.compile().invoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "cael_provenance",
                            "args": inputs,
                            "id": "authored-call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }
    )
    message = response["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.artifact == runtime.answer(inputs)
    assert verify(message.artifact, inputs, runtime)
    assert json.loads(message.content)["source_ids"] == ["s1", "s2", "s3"]


def test_real_checkpoint_resume_rechecks_unchanged_provenance(runtime):
    from langgraph.checkpoint.memory import InMemorySaver

    from cael_provenance.langgraph import graph_builder

    saver = InMemorySaver()
    graph = graph_builder(runtime).compile(
        checkpointer=saver, interrupt_after=["evaluate"]
    )
    config = {"configurable": {"thread_id": "proof-checkpoint"}}
    inputs = CASES[3][1]
    paused = graph.invoke({"request": inputs}, config)
    assert paused["verified"] is False
    saved = copy.deepcopy(graph.get_state(config).values["certificate"])
    resumed = graph_builder(runtime).compile(checkpointer=saver).invoke(None, config)
    assert resumed["verified"] is True
    assert resumed["certificate"] == saved


def test_checkpoint_tampering_fails_on_resume(runtime):
    from langgraph.checkpoint.memory import InMemorySaver

    from cael_provenance.langgraph import graph_builder

    graph = graph_builder(runtime).compile(
        checkpointer=InMemorySaver(), interrupt_after=["evaluate"]
    )
    config = {"configurable": {"thread_id": "tampered-checkpoint"}}
    inputs = CASES[3][1]
    paused = graph.invoke({"request": inputs}, config)
    forged = copy.deepcopy(paused["certificate"])
    forged["evidence"][0]["quote"] = "invented source"
    graph.update_state(config, {"certificate": forged})
    with pytest.raises(ProvenanceError):
        graph.invoke(None, config)


@pytest.mark.parametrize(
    "name,inputs,observed,intended", CASES, ids=[c[0] for c in CASES]
)
def test_actual_crewai_tool_and_flow(
    runtime, artifact_dir, name, inputs, observed, intended
):
    from cael_provenance.crewai import CAELProofTool, provenance_flow
    from cael_provenance.schema import ProofEnvelope

    tool = CAELProofTool(runtime)
    envelope = tool.run(**inputs)
    assert isinstance(envelope, ProofEnvelope)
    assert tool.result_as_answer is True
    assert envelope.model_dump(mode="json") == runtime.answer(inputs)
    flow = provenance_flow(runtime)
    result = flow.kickoff(inputs={"request": inputs})
    assert result["certificate"] == envelope.model_dump(mode="json")
    assert result["verified"] is (observed != "unsupported")
    (artifact_dir / ("crewai-" + name + ".json")).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
