import logging
import time
import re
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import BaseAgent
from agents.concept_interpreter import ConceptAnalysis, SubConcept
from agents.manim_models import (
    ScenePlan, SceneAction, ManimSceneCode, RenderResult,
    AnimationResult, AnimationConfig, AnimationMetadata
)
from rendering.manim_renderer import ManimRenderer


class ManimAgent(BaseAgent):
    """
    Manim Agent: Transforms structured concept analysis into visual animations
    using scene planning and Manim code generation with <manim> tag extraction.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        output_dir: Path,
        config: Optional[AnimationConfig] = None,
        reasoning_tokens: Optional[float] = None,
        reasoning_effort: Optional[str] = None
    ):
        super().__init__(api_key=api_key, base_url=base_url, model=model, reasoning_tokens=reasoning_tokens, reasoning_effort=reasoning_effort)
        self.output_dir = Path(output_dir)
        self.config = config or AnimationConfig()

        # Initialize renderer
        self.renderer = ManimRenderer(
            output_dir=self.output_dir / "scenes",
            quality=self.config.quality,
            background_color=self.config.background_color,
            timeout=self.config.render_timeout,
            max_retries=self.config.max_retries_per_scene
        )

        # Ensure output directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "scene_codes").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "animations").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "scenes").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "scene_plans").mkdir(parents=True, exist_ok=True)

    SCENE_PLANNING_PROMPT = """You are a Manim Scene Planning Agent for an educational STEM animation system.

**TASK**: Create detailed scene plans for animating STEM concepts using Manim (Mathematical Animation Engine).

**INPUT CONCEPT ANALYSIS**:
{concept_analysis}

**ANIMATION GUIDELINES**:

1. **Scene Structure**:
   - Create 1–2 scenes per sub-concept (maximum 8 scenes total)
   - Each scene should be 30–45 seconds long
   - Build scenes logically following sub-concept dependencies
   - Start with foundations, progressively add complexity

2. **Visual Design**:
   - Use clear, educational visual style (dark background, bright elements)
   - Include mathematical notation, equations, diagrams
   - Show relationships and transformations visually
   - Use color coding consistently:
     - Blue (#3B82F6) for known/assumed quantities
     - Green (#22C55E) for newly introduced concepts
     - Red (#EF4444) for key/important results or warnings

3. **Consistency & Continuity (VERY IMPORTANT)**:
   - If an illustrative example is used to demonstrate the concept (e.g., a specific array for a sorting algorithm, a fixed probability scenario, a single graph), **use the exact same example and values across all scenes** unless a scene explicitly explores a variant. 
   - Keep element IDs and targets stable across scenes (e.g., "example_array", "disease_prevalence_box") to preserve continuity.
   - Reuse and transform existing elements instead of recreating them where possible.

4. **Animation Types**:
   - write / create: introduce text, equations, axes, or diagrams
   - transform / replace: mathematical transformations, substitutions, rearrangements
   - fade_in / fade_out: introduce or remove elements
   - move / highlight: focus attention
   - grow / shrink: emphasize scale or importance
   - **wait**: insert a timed pause with nothing changing on screen (used for narration beats)

5. **Pacing & Narration Cues**:
   - Animations should be **slow and deliberate**. After each significant action (write, transform, highlight, etc.), insert a **wait** action of 1.5–3.0 seconds for narration.
   - Typical durations (guideline, adjust as needed):
     - write/create (short text/equation): 4–5s
     - transform/replace (equation/diagram): 8-19s
     - move/highlight: 3-5s
     - fade_in/out: 2-5s
     - wait (narration): 2-4s
   - Prefer easing that reads smoothly (ease-in-out). Include `"parameters": {"easing": "ease_in_out"}` when relevant.

6. **Educational Flow**:
   - Start with context/overview
   - Introduce new elements step-by-step
   - Show relationships and connections visually
   - End with key takeaways or summaries, keeping the same example visible to reinforce learning

7. **Element Naming**:
   - Use descriptive, stable targets (e.g., "bayes_equation", "likelihood_label", "frequency_grid") reused across scenes.
   - When transforming, specify `"parameters": {"from": "<old_target>", "to": "<new_target>"}` where helpful.

**OUTPUT FORMAT**:
Return ONLY valid JSON matching this exact structure:
{{
    "scene_plans": [
        {{
            "id": "string",
            "title": "string",
            "description": "string",
            "sub_concept_id": "string",
            "actions": [
                {{
                    "action_type": "string",
                    "element_type": "string",
                    "description": "string",
                    "target": "string",
                    "duration": number,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["string"]
        }}
    ]
}}

**EXAMPLE** for Bayes' Theorem (consistent example across all scenes: medical test with 1% prevalence, 90% sensitivity, 95% specificity):
{{
    "scene_plans": [
        {{
            "id": "intro_context",
            "title": "Bayes' Theorem: Context & Setup",
            "description": "Introduce the medical testing example and define prior, sensitivity, and specificity.",
            "sub_concept_id": "context_prior",
            "actions": [
                {{
                    "action_type": "fade_in",
                    "element_type": "text",
                    "description": "Display title 'Bayes' Theorem'",
                    "target": "title_text",
                    "duration": 2.0,
                    "parameters": {{"text": "Bayes' Theorem", "color": "#FFFFFF"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Narration pause after title",
                    "target": "narration_pause_1",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "write",
                    "element_type": "text",
                    "description": "Present consistent example scenario",
                    "target": "scenario_text",
                    "duration": 5.0,
                    "parameters": {{"text": "Medical test scenario: Disease prevalence 1%, Sensitivity 90%, Specificity 95%", "color": "#FFFFFF", "easing": "ease_in_out"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause for narrator to explain prevalence and test properties",
                    "target": "narration_pause_2",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "write",
                    "element_type": "math_equation",
                    "description": "Define prior and test properties with color coding",
                    "target": "definitions",
                    "duration": 6.0,
                    "parameters": {{"equation": "P(D)=0.01,\\ \\text{{sensitivity}}=0.90,\\ \\text{{specificity}}=0.95", "color": "#3B82F6", "easing": "ease_in_out"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Hold before moving on",
                    "target": "narration_pause_3",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "write",
                    "element_type": "diagram",
                    "description": "Draw a population box to anchor the example that persists across scenes",
                    "target": "population_box",
                    "duration": 6.0,
                    "parameters": {{"style": "outlined", "color": "#3B82F6", "label": "Population"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause to reinforce the setup",
                    "target": "narration_pause_4",
                    "duration": 3.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": []
        }},
        {{
            "id": "equation_intro",
            "title": "Bayes' Formula",
            "description": "Introduce Bayes' theorem and map terms to the example.",
            "sub_concept_id": "bayes_equation",
            "actions": [
                {{
                    "action_type": "write",
                    "element_type": "math_equation",
                    "description": "Write Bayes' theorem",
                    "target": "bayes_equation",
                    "duration": 4.0,
                    "parameters": {{"equation": "P(D\\mid +)=\\frac{{P(+\\mid D)P(D)}}{{P(+)}}", "color": "#22C55E", "easing": "ease_in_out"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause to read equation",
                    "target": "narration_pause_5",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "write",
                    "element_type": "text",
                    "description": "Label terms: prior, likelihood, evidence, posterior",
                    "target": "term_labels",
                    "duration": 5.0,
                    "parameters": {{"text": "prior: P(D) (blue), likelihood: P(+|D) (green), evidence: P(+) (white), posterior: P(D|+) (red)", "color": "#FFFFFF"}}
                }},
                {{
                    "action_type": "highlight",
                    "element_type": "math_equation",
                    "description": "Color-code terms on the formula",
                    "target": "bayes_equation",
                    "duration": 3.0,
                    "parameters": {{"spans": [{{"term": "P(D)", "color": "#3B82F6"}}, {{"term": "P(+\\mid D)", "color": "#22C55E"}}, {{"term": "P(+)", "color": "#FFFFFF"}}, {{"term": "P(D\\mid +)", "color": "#EF4444"}}]}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Narration pause after mapping",
                    "target": "narration_pause_6",
                    "duration": 2.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["intro_context"]
        }},
        {{
            "id": "tree_diagram",
            "title": "Likelihood Paths via Tree",
            "description": "Show a probability tree aligned with the same example numbers.",
            "sub_concept_id": "likelihood_evidence",
            "actions": [
                {{
                    "action_type": "write",
                    "element_type": "diagram",
                    "description": "Draw tree branches for D and ¬D from population",
                    "target": "probability_tree",
                    "duration": 6.0,
                    "parameters": {{"from": "population_box", "branches": [{{"label": "D (1%)", "color": "#3B82F6"}}, {{"label": "¬D (99%)", "color": "#3B82F6"}}]}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause for narrator to explain branches",
                    "target": "narration_pause_7",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "write",
                    "element_type": "diagram",
                    "description": "Add test outcome branches with sensitivity/specificity",
                    "target": "probability_tree_outcomes",
                    "duration": 6.0,
                    "parameters": {{"branches": [{{"from": "D", "label": "+ (90%)", "color": "#22C55E"}}, {{"from": "D", "label": "− (10%)", "color": "#22C55E"}}, {{"from": "¬D", "label": "+ (5%)", "color": "#22C55E"}}, {{"from": "¬D", "label": "− (95%)", "color": "#22C55E"}}]}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause after outcomes",
                    "target": "narration_pause_8",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "highlight",
                    "element_type": "diagram",
                    "description": "Highlight the evidence paths that lead to '+'",
                    "target": "probability_tree_outcomes",
                    "duration": 3.0,
                    "parameters": {{"paths": ["D→+", "¬D→+"], "color": "#EF4444"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Hold to emphasize 'evidence' P(+)",
                    "target": "narration_pause_9",
                    "duration": 2.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["intro_context", "equation_intro"]
        }},
        {{
            "id": "frequency_view",
            "title": "Frequency Grid Intuition",
            "description": "Use a 10,000-dot grid to make P(+) and P(D|+) concrete with the same numbers.",
            "sub_concept_id": "evidence_frequency",
            "actions": [
                {{
                    "action_type": "write",
                    "element_type": "diagram",
                    "description": "Create 10,000-dot grid inside population box (persists across scenes)",
                    "target": "frequency_grid",
                    "duration": 6.0,
                    "parameters": {{"rows": 100, "cols": 100, "color": "#555555", "parent": "population_box"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause for narrator to explain frequency framing",
                    "target": "narration_pause_10",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "highlight",
                    "element_type": "diagram",
                    "description": "Color 100 diseased dots (1%) in blue",
                    "target": "frequency_grid_D",
                    "duration": 4.0,
                    "parameters": {{"count": 100, "color": "#3B82F6"}}
                }},
                {{
                    "action_type": "highlight",
                    "element_type": "diagram",
                    "description": "Among D, highlight 90 true positives in green",
                    "target": "frequency_grid_TP",
                    "duration": 4.0,
                    "parameters": {{"count": 90, "color": "#22C55E"}}
                }},
                {{
                    "action_type": "highlight",
                    "element_type": "diagram",
                    "description": "Among ¬D, highlight 495 false positives (5% of 9,900) in green outline",
                    "target": "frequency_grid_FP",
                    "duration": 5.0,
                    "parameters": {{"count": 495, "style": "outline", "color": "#22C55E"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Hold to let counts sink in",
                    "target": "narration_pause_11",
                    "duration": 3.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["intro_context", "equation_intro", "tree_diagram"]
        }},
        {{
            "id": "posterior_compute",
            "title": "Compute P(D|+)",
            "description": "Compute the posterior step-by-step using the same counts and Bayes' formula.",
            "sub_concept_id": "posterior_computation",
            "actions": [
                {{
                    "action_type": "write",
                    "element_type": "math_equation",
                    "description": "Substitute numeric values into Bayes' formula",
                    "target": "substitution",
                    "duration": 5.0,
                    "parameters": {{"equation": "P(D\\mid +)=\\frac{{0.90\\times 0.01}}{{0.90\\times 0.01 + 0.05\\times 0.99}}", "color": "#FFFFFF"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause for narrator before simplifying",
                    "target": "narration_pause_12",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "transform",
                    "element_type": "math_equation",
                    "description": "Simplify numerators and denominators",
                    "target": "substitution",
                    "duration": 4.0,
                    "parameters": {{"to_equation": "P(D\\mid +)=\\frac{{0.009}}{{0.009+0.0495}}", "color": "#FFFFFF", "easing": "ease_in_out"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause before final result",
                    "target": "narration_pause_13",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "transform",
                    "element_type": "math_equation",
                    "description": "Compute final posterior and highlight",
                    "target": "substitution",
                    "duration": 4.0,
                    "parameters": {{"to_equation": "P(D\\mid +)\\approx 0.1538\\ (15.38\\%)", "color": "#EF4444", "easing": "ease_in_out"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Hold on final posterior",
                    "target": "narration_pause_14",
                    "duration": 3.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["equation_intro", "frequency_view"]
        }},
        {{
            "id": "interpretation_pitfalls",
            "title": "Interpretation & Common Pitfall",
            "description": "Explain why a positive test doesn't mean near-certainty; connect to base rates.",
            "sub_concept_id": "interpretation",
            "actions": [
                {{
                    "action_type": "write",
                    "element_type": "text",
                    "description": "State the common mistake: confusing P(+|D) with P(D|+)",
                    "target": "pitfall_text",
                    "duration": 4.0,
                    "parameters": {{"text": "Pitfall: P(+|D) \\neq P(D|+)", "color": "#EF4444"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Pause for narrator",
                    "target": "narration_pause_15",
                    "duration": 2.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "highlight",
                    "element_type": "diagram",
                    "description": "Re-highlight 90 TP vs 495 FP on the same grid to show contrast",
                    "target": "frequency_grid_contrast",
                    "duration": 4.0,
                    "parameters": {{"groups": [{{"label": "TP=90", "color": "#22C55E"}}, {{"label": "FP=495", "color": "#EF4444"}}]}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Hold to let the contrast register",
                    "target": "narration_pause_16",
                    "duration": 3.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["posterior_compute"]
        }},
        {{
            "id": "summary_takeaways",
            "title": "Summary & Takeaways",
            "description": "Summarize Bayes' theorem using the same scenario and numbers.",
            "sub_concept_id": "summary",
            "actions": [
                {{
                    "action_type": "write",
                    "element_type": "text",
                    "description": "List key takeaways linked to the same example",
                    "target": "summary_points",
                    "duration": 6.0,
                    "parameters": {{"text": "1) Base rates matter. 2) Evidence combines with prior via likelihood. 3) Posterior here ≈ 15.38%.", "color": "#FFFFFF"}}
                }},
                {{
                    "action_type": "wait",
                    "element_type": "none",
                    "description": "Final narration pause",
                    "target": "narration_pause_17",
                    "duration": 3.0,
                    "parameters": {{}}
                }},
                {{
                    "action_type": "fade_out",
                    "element_type": "group",
                    "description": "Fade out all elements to close",
                    "target": "all_elements",
                    "duration": 2.0,
                    "parameters": {{}}
                }}
            ],
            "scene_dependencies": ["interpretation_pitfalls"]
        }}
    ]
}}

Generate scene plans that will create clear, educational animations for the given concept, using a single consistent example across scenes, with slow pacing and explicit narration pauses after each major action."""

    CODE_GENERATION_PROMPT = """You are a Manim Code Generation Agent for creating **very simple, 2D educational STEM animations**.

**TASK**: From the single **SCENE PLAN** below (one scene at a time), generate complete, executable Manim code for **Manim Community Edition v0.19** that faithfully renders the specified actions with slow, narrator-friendly pacing.

**SCENE PLAN (SINGLE SCENE ONLY)**:
{scene_plan}

**CLASS NAME**: {class_name}
**TARGET DURATION (approx.)**: {target_duration} seconds

============================================================
SIMPLE 2D-ONLY MODE (STRICT)
============================================================

0) **Hard Limits (Do Not Violate)**
   - **2D only**: No 3D classes/cameras/surfaces/axes3D; do not import/use `ThreeDScene`.
   - **Exactly one scene class** named **{class_name}**, inheriting from `Scene`.
   - **One file**, **one class**, **one `construct(self)`** method.
   - **No updaters** (no `add_updater`, no `always_redraw`).
   - **No ValueTracker / DecimalNumber**; keep logic static and stepwise.
   - **No config edits**, no camera/frame changes, no run_time tweaks (use `self.wait()` only).

1) **Imports**
   - Always start with: `from manim import *`
   - Optionally: `import numpy as np` **only if actually used**.
   - Import nothing else.

2) **Element Types & Mapping**
   - Use **`Text`** for plain text, **`MathTex`** for math, **`Tex`** for LaTeX (non-math).
   - Allowed 2D mobjects: `Dot, Line, Arrow, Vector, Circle, Square, Rectangle, Triangle, NumberPlane, Axes, Brace, SurroundingRectangle, Text, MathTex, Tex, VGroup`.
   - Unsupported elements in the plan (e.g., complex "diagram" types) must be **downgraded** to simple shapes + labels (e.g., boxes, lines, arrows, small groups of dots).

2a) **Safe Zone for Subtitles (Important)**
   - Burned-in subtitles occupy the **bottom ~22%** of the frame.
   - **Never place text, formulas, or important visuals in the bottom 22%** of the screen (`y < -3.0` in Manim's default 16:9 frame of y in `[-4, 4]`).
   - Place all `Text` / `MathTex` / `Tex` in the **upper region** with `y >= -2.5` (e.g. `text.shift(UP * 2.5)`), or shift the whole group upward with `.to_edge(UP)` / `.shift(UP * 0.5)`.
   - If a scene's main content must be near the bottom, **raise it first** (e.g. `obj.shift(UP * 1.5)`) so the subtitle band stays clear.
   - Title / heading text is fine at the very top; long explanations belong in the **middle band** (`y` roughly in `[-1.5, 2.5]`).
   - Treat `y < -2.5` as the "subtitle keep-out zone" — nothing else should live there.
   - Avoid `self.add(text)` at default Manim center for important text; explicitly position it to keep the bottom band clear.

3) **Action → Code Mapping (Use Only These)**
   - `"write"` → `self.play(Write(obj))`
   - `"create"` → `self.play(Create(obj))`
   - `"fade_in"` / `"fade_out"` → `FadeIn(obj)` / `FadeOut(obj)`
   - `"transform"` → `Transform(old, new)` (both must exist/added)
   - `"replacement_transform"` → `ReplacementTransform(old, new)`
   - `"move"` → `obj.animate.shift(DIR * amount)`
   - `"highlight"` → Prefer `Indicate(obj)`; or show a `SurroundingRectangle(obj)` with `FadeIn`/`FadeOut`
   - `"wait"` → `self.wait(duration)`
   - Any other `action_type` not listed → use nearest allowed mapping or **skip with a short comment** (still respect pacing).

4) **Using `target` as Variable Names (Continuity)**
   - For each action, **use the plan’s `"target"` as the Python variable name** (sanitize to snake_case, alphanumerics + underscores).
   - Reuse the same variable to transform/indicate; do **not** recreate after `FadeOut` unless the plan explicitly reintroduces it.
   - If the SCENE PLAN references elements created in earlier scenes, **stub a minimal placeholder** (e.g., a labeled `Rectangle` or `Text`) consistent with the example, so this scene remains executable without cross-scene state.

5) **Parameters Handling**
   - Map common fields directly:
     - `{{"text": "..."}}` → Text(...) or Tex(...)
     - `{{"equation": "..."}}` → MathTex(r"...")
     - `{{"color": BUILTIN_COLOR}}`
   - **Colors (Built-ins Only)**: `WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, PINK`. **Never use CYAN.**
   - If plan provides hex colors (e.g., `#3B82F6`), **replace with the closest built-in** (e.g., `BLUE`, `GREEN`, `RED`, `WHITE`).
   - Ignore unsupported params silently; keep code minimal.

6) **Pacing & Narration (Derived from Plan)**
   - After **every significant action**, insert a pause:  
     `pause = clamp(round(action.duration * 0.5), 1, 3)` → `self.wait(pause)`
   - If an explicit `"wait"` action appears, honor its `"duration"` directly (clamp to [1, 4] if very large).
   - Animations should feel **slow and deliberate**; do **not** chain many animations without waits.

7) **Layout & Anti-overlap Heuristics**
   - Keep a simple, readable layout:
     - Optional title near top: `to_edge(UP)`
     - Main content centered; secondary labels `next_to(...)`
   - Prefer `next_to`, `to_edge`, small `shift` values; avoid dense stacking.
   - If multiple texts/equations appear, place them **vertically** with `next_to(prev, DOWN)`.
   - Keep font sizes moderate (e.g., `Text(..., font_size=36–48)`) to avoid overflow.
   - Keep explaination text, calculation and the visualization seperate to avoid overlapping

8) **Flow (Minimal & Clear)**
   - Brief title (2–3s), then step-by-step reveal matching the order of `actions`.
   - Insert `self.wait(1)` **at minimum** between logical steps if the plan’s duration is missing.
   - End with `self.wait(2)` holding the final state.

9) **Graceful Downgrades for Heavy Visuals**
   - Large “grids” or thousands of dots: substitute a labeled `Rectangle` or a **small** `VGroup` (≤ 20 dots) plus a label like `"10,000 cases (schematic)"`.
   - Complex “tree diagrams”: approximate with `Line` + `Text` labels; keep branches ≤ 4 elements.

10) **Robustness**
   - Ensure each mobject is **created/added** before transforming/indicating it.
   - Do not reference objects after `FadeOut` unless re-created.
   - Only allowed animations/mobjects; **no** camera moves, seeds, randomness, external assets, or experimental APIs.
   - Make sure that your code match with the concept we are tring to visualize.
   - The visualization must be correct and reflect the topic being shown since this will affect the learning outcome.
   - Avoid using uncommon parameters and methods in your code.

11) **Consistency with the Planner’s Example**
   - **Do not change** numeric values or scenario details present in this scene plan (this preserves cross-scene example consistency).
   - Keep variable names identical to `"target"` (post-sanitization) across all actions in this scene.

12) **DO NOT INCLUDE BACKTICKS (``) IN YOUR CODE, EVER!**

**GUIDELINE**:
- Skim through the scence and think of a draft version.
- Make sure to iterate through the code to make sure all the codes are correct.
- You have to make sure that all elements are created and placed correctly on the scene.

============================================================
OUTPUT FORMAT (MANDATORY)
============================================================
<manim>
from manim import *
# Manim Community v0.19 — Simple 2D Scene

class {class_name}(Scene):
    def construct(self):
        # Optional title (avoid overlap by placing at top)
        # title = Text("Your Title", font_size=48).to_edge(UP)
        # self.play(Write(title)); self.wait(2)

        # Map actions in order from the SCENE PLAN:
        # Example mappings (replace with this scene's real actions):
        # eq = MathTex(r"P(D\\mid +)=\\frac{{P(+\\mid D)P(D)}}{{P(+)}}", color=WHITE)
        # self.play(Write(eq)); self.wait(2)
        # box = Rectangle(width=5, height=3, color=BLUE)
        # self.play(Create(box)); self.wait(1)
        # hl = SurroundingRectangle(eq, color=RED)
        # self.play(Create(hl)); self.wait(1); self.play(FadeOut(hl))
        # self.play(eq.animate.shift(DOWN*1.2)); self.wait(2)

        self.wait(2)
</manim>
"""

    def execute(self, concept_analysis: ConceptAnalysis) -> AnimationResult:

        start_time = time.time()
        self.logger.info(f"Starting animation generation for: {concept_analysis.main_concept}")

        try:
            # Step 1: Generate scene plans
            scene_plans, response_json = self._generate_scene_plans(concept_analysis)
            self.logger.info(f"Generated {len(scene_plans)} scene plans")

            # Save scene plans for debugging
            self._save_scene_plans(scene_plans, concept_analysis, response_json)

            # Step 2: Generate Manim code for each scene
            scene_codes = self._generate_scene_codes(scene_plans)
            self.logger.info(f"Generated code for {len(scene_codes)} scenes")

            # Step 3: Render each scene
            render_results = self._render_scenes(scene_codes)
            successful_renders = [r for r in render_results if r.success]
            self.logger.info(f"Successfully rendered {len(successful_renders)}/{len(render_results)} scenes")

            # Step 4: Concatenate scenes into single animation
            if successful_renders:
                silent_animation_path = self._concatenate_scenes(successful_renders)
            else:
                silent_animation_path = None

            # Calculate timing
            generation_time = time.time() - start_time
            total_render_time = sum(r.render_time or 0 for r in render_results)

            # Create result
            result = AnimationResult(
                success=len(successful_renders) > 0,
                concept_id=concept_analysis.main_concept.lower().replace(" ", "_"),
                total_duration=sum(r.duration for r in successful_renders if r.duration),
                scene_count=len(scene_plans),
                silent_animation_path=str(silent_animation_path) if silent_animation_path else None,
                scene_plan=scene_plans,
                scene_codes=scene_codes,
                render_results=render_results,
                generation_time=generation_time,
                total_render_time=total_render_time,
                models_used={"reasoning": self.model},
                token_usage=self.get_token_usage()
            )

            self.logger.info(f"Animation generation completed in {generation_time:.2f}s")
            return result

        except Exception as e:
            self.logger.error(f"Animation generation failed: {e}")
            return AnimationResult(
                success=False,
                concept_id=concept_analysis.main_concept.lower().replace(" ", "_"),
                scene_count=0,
                error_message=str(e),
                scene_plan=[],
                scene_codes=[],
                render_results=[],
                generation_time=time.time() - start_time,
                models_used={"reasoning": self.model},
                token_usage=self.get_token_usage()
            )

    def _generate_scene_plans(self, concept_analysis: ConceptAnalysis) -> tuple[List[ScenePlan], Dict[str, Any]]:
        """Generate scene plans from concept analysis"""

        user_message = f"Analyze this STEM concept and create scene plans:\n\n{json.dumps(concept_analysis.model_dump(), indent=2)}"

        try:
            response_json = self._call_llm_structured(
                system_prompt=self.SCENE_PLANNING_PROMPT,
                user_message=user_message,
                temperature=self.config.temperature,
                max_retries=3
            )

            # Parse and validate scene plans
            scene_plans = []
            for plan_data in response_json.get("scene_plans", []):
                try:
                    scene_plan = ScenePlan(**plan_data)
                    scene_plans.append(scene_plan)
                except Exception as e:
                    self.logger.warning(f"Invalid scene plan data: {e}")
                    continue

            return scene_plans, response_json

        except Exception as e:
            self.logger.error(f"Scene planning failed: {e}")
            raise ValueError(f"Failed to generate scene plans: {e}")

    def _save_scene_plans(self, scene_plans: List[ScenePlan], concept_analysis: ConceptAnalysis, response_json: Dict[str, Any]) -> Path:
        """Save raw scene plans output to JSON file for debugging"""

        # Generate filename from concept
        safe_name = "".join(c if c.isalnum() else "_" for c in concept_analysis.main_concept.lower())
        safe_name = safe_name[:50]  # Limit length
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_raw_scene_plans_{timestamp}.json"

        filepath = self.output_dir / "scene_plans" / filename

        # Save raw response
        with open(filepath, 'w') as f:
            json.dump(response_json, f, indent=2)

        self.logger.info(f"Raw scene plans output saved to {filepath}")
        return filepath

    def _generate_scene_codes(self, scene_plans: List[ScenePlan]) -> List[ManimSceneCode]:
        """Generate Manim code for each scene plan in parallel"""

        scene_codes = []
        self.logger.info(f"Starting parallel code generation for {len(scene_plans)} scenes")

        def generate_single_scene_code(scene_plan: ScenePlan) -> Optional[ManimSceneCode]:
            """Generate code for a single scene"""
            try:
                self.logger.info(f"Generating code for scene: {scene_plan.title}")
                self.logger.debug(f"Scene ID: {scene_plan.id}, Actions count: {len(scene_plan.actions)}")

                class_name = self._sanitize_class_name(scene_plan.id)
                self.logger.debug(f"Sanitized class name: {class_name}")

                # Log the scene plan for debugging
                scene_plan_json = json.dumps(scene_plan.model_dump(), indent=2)
                self.logger.debug(f"Scene plan JSON length: {len(scene_plan_json)} characters")
                self.logger.debug(f"First action parameters: {scene_plan.actions[0].parameters if scene_plan.actions else 'N/A'}")

                try:
                    formatted_prompt = self.CODE_GENERATION_PROMPT.format(
                        scene_plan=scene_plan_json,
                        class_name=class_name,
                        target_duration="25-30"
                    )
                    self.logger.debug(f"System prompt formatted successfully, length: {len(formatted_prompt)}")
                except Exception as fmt_error:
                    self.logger.error(f"Failed to format system prompt: {fmt_error}")
                    self.logger.error(f"Format error type: {type(fmt_error).__name__}")
                    raise

                response = self._call_llm(
                    system_prompt=formatted_prompt,
                    user_message="Generate the Manim code for the scene plan specified above.",
                    temperature=self.config.temperature,
                    max_retries=3
                )

                self.logger.debug(f"LLM response received, length: {len(response)} characters")
                self.logger.debug(f"Response preview: {response[:200]}...")

                manim_code, extraction_method = self._extract_manim_code(response)
                self.logger.debug(f"Code extraction method: {extraction_method}")

                if manim_code:
                    self.logger.debug(f"Extracted code length: {len(manim_code)} characters")
                    self._save_scene_code(scene_plan.id, class_name, manim_code, response)

                    scene_code = ManimSceneCode(
                        scene_id=scene_plan.id,
                        scene_name=class_name,
                        manim_code=manim_code,
                        raw_llm_output=response,
                        extraction_method=extraction_method
                    )

                    self.logger.info(f"Successfully generated code for scene: {class_name}")
                    return scene_code
                else:
                    self.logger.error(f"Failed to extract Manim code from response for scene: {scene_plan.id}")
                    self.logger.error(f"Response contained: {response[:500]}...")
                    return None

            except Exception as e:
                self.logger.error(f"Code generation failed for scene {scene_plan.id}: {e}")
                self.logger.error(f"Exception type: {type(e).__name__}")
                self.logger.error(f"Exception details: {str(e)}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                return None

        concurrency = max(1, min(self.config.code_gen_concurrency, len(scene_plans)))
        self.logger.info(f"Using concurrency: {concurrency}")
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_plan = {executor.submit(generate_single_scene_code, plan): plan for plan in scene_plans}
            
            for future in as_completed(future_to_plan):
                scene_plan = future_to_plan[future]
                try:
                    result = future.result()
                    if result:
                        scene_codes.append(result)
                except Exception as e:
                    self.logger.error(f"Exception in parallel code generation for {scene_plan.id}: {e}")

        scene_codes.sort(key=lambda x: scene_plans.index(next(p for p in scene_plans if p.id == x.scene_id)))
        self.logger.info(f"Parallel code generation complete: {len(scene_codes)}/{len(scene_plans)} succeeded")

        return scene_codes

    def _extract_manim_code(self, response: str) -> tuple[str, str]:
        """Extract Manim code from LLM response using <manim> tags"""

        # Method 1: Try to extract from <manim>...</manim> tags
        manim_pattern = r'<manim>(.*?)</manim>'
        matches = re.findall(manim_pattern, response, re.DOTALL)

        if matches:
            # Take the first (most complete) match
            manim_code = matches[0].strip()
            # Clean the code by removing backticks
            manim_code = self._clean_manim_code(manim_code)
            return manim_code, "tags"

        # Method 2: Try to extract class definition if no tags found
        class_pattern = r'class\s+(\w+)\s*\(\s*Scene\s*\):.*?(?=\n\nclass|\Z)'
        matches = re.findall(class_pattern, response, re.DOTALL)

        if matches:
            # Find the complete code block
            class_start = response.find(f"class {matches[0]}(")
            if class_start != -1:
                # Find the end of this class (next class or end of response)
                remaining = response[class_start:]
                next_class = re.search(r'\n\nclass\s+\w+', remaining)
                if next_class:
                    manim_code = remaining[:next_class.start()]
                else:
                    manim_code = remaining

                # Add imports if missing
                if "from manim import" not in manim_code:
                    manim_code = "from manim import *\n\n" + manim_code

                # Clean the code by removing backticks
                manim_code = self._clean_manim_code(manim_code)
                return manim_code.strip(), "parsing"

        # Method 3: Last resort - try to fix common formatting issues
        if "class" in response and "def construct" in response:
            # Basic cleanup
            cleaned = response.strip()
            if not cleaned.startswith("from"):
                cleaned = "from manim import *\n\n" + cleaned

            # Clean the code by removing backticks
            cleaned = self._clean_manim_code(cleaned)
            return cleaned, "cleanup"

        return "", "failed"

    def _clean_manim_code(self, code: str) -> str:
        """Clean Manim code by removing backticks and fixing common issues"""

        # Remove all backticks - this is the main issue
        code = code.replace('`', '')

        # Fix common triple-backtick code block markers that might leave extra formatting
        code = re.sub(r'python\n', '', code, flags=re.IGNORECASE)
        code = re.sub(r'\npython', '', code, flags=re.IGNORECASE)

        # Remove any remaining markdown-style code formatting
        code = re.sub(r'^```.*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n```.*$', '', code, flags=re.MULTILINE)

        # Clean up any double newlines that might have been created
        code = re.sub(r'\n{3,}', '\n\n', code)

        # Strip leading/trailing whitespace
        code = code.strip()

        # Add UTF-8 encoding declaration for Windows compatibility
        if not code.startswith('# -*- coding'):
            code = "# -*- coding: utf-8 -*-\n" + code

        # Log the cleaning if significant changes were made
        original_length = len(code.replace('`', ''))
        if original_length != len(code):
            self.logger.debug("Applied Manim code cleaning (removed backticks and formatting)")

        return code

    def _sanitize_class_name(self, scene_id: str) -> str:
        """Convert scene ID to valid Python class name"""
        # Remove invalid characters and convert to PascalCase
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', scene_id)
        # Capitalize first letter and ensure it starts with letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = "Scene_" + sanitized
        sanitized = sanitized.title().replace('_', '')

        # Ensure it's not empty
        if not sanitized:
            sanitized = "AnimationScene"

        return sanitized

    def _save_scene_code(self, scene_id: str, class_name: str, manim_code: str, raw_output: str) -> Path:
        """Save generated Manim code to file"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scene_id}_{class_name}_{timestamp}.py"
        filepath = self.output_dir / "scene_codes" / filename

        # Save both the clean code and raw output for debugging
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Generated Manim code for scene: {scene_id}\n")
            f.write(f"# Class: {class_name}\n")
            f.write(f"# Generated at: {timestamp}\n\n")
            f.write(manim_code)

        # Also save raw LLM output
        raw_filepath = filepath.with_suffix('.raw.txt')
        with open(raw_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Raw LLM output for scene: {scene_id}\n")
            f.write(f"# Class: {class_name}\n")
            f.write(f"# Generated at: {timestamp}\n\n")
            f.write(raw_output)

        return filepath

    def _render_scenes(self, scene_codes: List[ManimSceneCode]) -> List[RenderResult]:
        """Render each scene using ManimRenderer"""

        render_results = []

        for scene_code in scene_codes:
            self.logger.info(f"Rendering scene: {scene_code.scene_name}")

            # Generate output filename
            output_filename = f"{scene_code.scene_id}_{scene_code.scene_name}.mp4"

            try:
                # Use renderer to create the video
                render_result = self.renderer.render(
                    manim_code=scene_code.manim_code,
                    scene_name=scene_code.scene_name,
                    output_filename=output_filename
                )

                # Convert to our RenderResult format
                result = RenderResult(
                    scene_id=scene_code.scene_id,
                    success=render_result.success,
                    video_path=render_result.video_path,
                    error_message=render_result.error_message,
                    duration=render_result.duration,
                    resolution=render_result.resolution,
                    render_time=render_result.render_time
                )

                render_results.append(result)

                if result.success:
                    self.logger.info(f"Successfully rendered: {scene_code.scene_name}")
                    self.logger.info(f"  Video path: {result.video_path}")
                    self.logger.info(f"  Duration: {result.duration}s")
                else:
                    self.logger.error(f"Failed to render {scene_code.scene_name}: {result.error_message}")

            except Exception as e:
                self.logger.error(f"Rendering failed for {scene_code.scene_name}: {e}")
                render_results.append(RenderResult(
                    scene_id=scene_code.scene_id,
                    success=False,
                    error_message=str(e)
                ))

        return render_results

    def _concatenate_scenes(self, render_results: List[RenderResult]) -> Optional[Path]:
        """Concatenate rendered scenes into single silent animation"""

        if not render_results:
            self.logger.error("No render results to concatenate")
            return None

        # Get video paths and convert to absolute paths
        video_paths = []
        for r in render_results:
            if r.success and r.video_path:
                video_path = Path(r.video_path)
                if not video_path.is_absolute():
                    video_path = (Path.cwd() / video_path).resolve()
                if video_path.exists():
                    video_paths.append(video_path)
                else:
                    self.logger.warning(f"Video path does not exist: {video_path}")

        if not video_paths:
            self.logger.error("No successfully rendered scenes with valid video paths to concatenate")
            self.logger.error(f"Render results: {[(r.scene_id, r.success, r.video_path) for r in render_results]}")
            return None

        self.logger.info(f"Found {len(video_paths)} videos to concatenate")

        try:
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"animation_{timestamp}.mp4"
            output_path = self.output_dir / "animations" / output_filename

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Use FFmpeg to concatenate videos
            self.logger.info(f"Concatenating {len(video_paths)} scenes into {output_filename}")

            # Create a temporary file with list of input videos (use absolute paths)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                for video_path in video_paths:
                    # Ensure absolute path and escape single quotes
                    abs_path = str(video_path.resolve())
                    temp_file.write(f"file '{abs_path}'\n")
                    self.logger.debug(f"Adding to concat list: {abs_path}")
                temp_file_path = temp_file.name

            try:
                # FFmpeg concat command with absolute paths
                cmd = [
                    "ffmpeg",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(temp_file_path),
                    "-c", "copy",
                    "-y",  # Overwrite output file if exists
                    str(output_path.resolve())
                ]

                self.logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0 and output_path.exists():
                    self.logger.info(f"Successfully concatenated animation: {output_filename}")
                    self.logger.info(f"Final video path: {output_path}")
                    return output_path
                else:
                    self.logger.error(f"FFmpeg concatenation failed with return code {result.returncode}")
                    self.logger.error(f"STDERR: {result.stderr}")
                    self.logger.error(f"STDOUT: {result.stdout}")
                    self.logger.error(f"Output path exists: {output_path.exists()}")
                    return None

            finally:
                # Clean up temporary file
                try:
                    import os
                    os.unlink(temp_file_path)
                except OSError:
                    pass

        except Exception as e:
            self.logger.error(f"Scene concatenation failed: {e}")
            return None

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get statistics about animation generation performance"""
        return {
            "token_usage": self.get_token_usage(),
            "model_used": self.model,
            "reasoning_tokens": self.reasoning_tokens,
            "config": self.config.model_dump(),
            "renderer_status": "ready" if self.renderer.validate_manim_installation() else "not_ready"
        }