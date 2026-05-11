# Graph Report - instagram autopost  (2026-05-11)

## Corpus Check
- 3 files · ~6,538 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 56 nodes · 111 edges · 9 communities detected
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]

## God Nodes (most connected - your core abstractions)
1. `main()` - 15 edges
2. `generate_caption()` - 9 edges
3. `process_pending_videos()` - 7 edges
4. `run_loop()` - 7 edges
5. `InstagramPoster` - 6 edges
6. `main()` - 6 edges
7. `_load_schedule_state()` - 4 edges
8. `_start_engine()` - 4 edges
9. `_fallback_caption()` - 4 edges
10. `_ollama_client()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `_ensure_directories()`  [EXTRACTED]
  app.py → app.py  _Bridges community 6 → community 2_
- `main()` --calls--> `_load_schedule_state()`  [EXTRACTED]
  app.py → app.py  _Bridges community 3 → community 2_
- `main()` --calls--> `_render_live_log()`  [EXTRACTED]
  app.py → app.py  _Bridges community 8 → community 2_
- `process_pending_videos()` --calls--> `ensure_directories()`  [EXTRACTED]
  core_pipeline.py → core_pipeline.py  _Bridges community 5 → community 7_
- `process_pending_videos()` --calls--> `InstagramPoster`  [EXTRACTED]
  core_pipeline.py → core_pipeline.py  _Bridges community 4 → community 7_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.32
Nodes (12): _build_prompt(), _call_ollama(), CaptionResult, _cleanup_caption(), _fallback_caption(), _fallback_hashtags(), generate_caption(), _get_ollama_config() (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.38
Nodes (8): _enabled_slot_times(), _enabled_slots(), load_scheduler_slots(), _next_slot_in_minutes(), _parse_hhmm(), run_loop(), SchedulerSlot, _slot_minutes()

### Community 2 - "Community 2"
Cohesion: 0.29
Nodes (8): _count_files(), _inject_css(), _load_session_value(), main(), _ollama_status(), _process_is_running(), _read_pid(), _stop_engine()

### Community 3 - "Community 3"
Cohesion: 0.38
Nodes (5): _default_slots(), _load_schedule_state(), _normalize_slots(), _render_directory_expander(), _save_schedule_state()

### Community 4 - "Community 4"
Cohesion: 0.53
Nodes (2): InstagramPoster, _read_sessionid()

### Community 5 - "Community 5"
Cohesion: 0.67
Nodes (4): configure_logging(), ensure_directories(), main(), write_pid_file()

### Community 6 - "Community 6"
Cohesion: 0.67
Nodes (3): _ensure_directories(), _save_sessionid(), _start_engine()

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (3): process_pending_videos(), run_once(), _safe_move()

### Community 8 - "Community 8"
Cohesion: 1.0
Nodes (2): _render_live_log(), _tail_log()

## Knowledge Gaps
- **Thin community `Community 4`** (6 nodes): `InstagramPoster`, `.__init__()`, `._login_with_sessionid()`, `.post_file()`, `._upload_reel()`, `_read_sessionid()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 8`** (2 nodes): `_render_live_log()`, `_tail_log()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_caption()` connect `Community 0` to `Community 4`?**
  _High betweenness centrality (0.193) - this node is a cross-community bridge._
- **Why does `process_pending_videos()` connect `Community 7` to `Community 1`, `Community 4`, `Community 5`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `InstagramPoster` connect `Community 4` to `Community 1`, `Community 7`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._