# Logic session controls

Use current connector/UI documentation. Treat labels, key commands and layout as version/keymap dependent. Never bake screen coordinates or track numbers into a reusable run.

- Inspect the open project after resuming: the user may have continued producing. Preserve their current work.
- Focus the destination track header, inspect state, then open its instrument or import. Selecting a region alone may leave another track focused. Instrument slots move vertically with effect counts.
- Re-query state between dependent actions; derive fresh accessibility identities. Confirm dialog title, track name and sample filename after loading.
- Stop playback/disable cycle temporarily when establishing origin. Verify the position numerically; Go to Beginning can act differently during cycle playback.
- Single-track MIDI import may use another track, create a piano track or insert at the playhead. Confirm destination and start after import. If necessary, cut the imported region, focus the correct header, set origin and paste, then inspect again. Remove only confirmed temporary tracks.
- Keep project tempo when an import asks to replace tempo, unless intentionally importing a validated tempo map.
- Expand Drum Machine Designer only when editing pad channels; verify its input/output note routing. Inspect sampler filenames and audition each pad. Prefer an empty kit or remove unused factory routing safely.
- Use supported sampler file-load controls. Controls view can expose parameters missing from Editor accessibility; pitch tracking can be disabled there. A factory preset name is not proof of the sample loaded.
- Use file-dialog Go to Folder for absolute paths. Entering a path into Save As may create a filename containing colons instead of changing folders. Confirm actual save location.
- If a long path fails, a short temporary staging path may help. Copy sampler media into the project and reopen without staging before handoff.
- Change approach after two unchanged clicks/drags. Treat AX errors and "user changed" messages as reasons to inspect fresh state, not proof the user interfered. Do not repeatedly blame or ask them to stop interacting.
- Avoid binary patching undocumented sampler/project files as a standard route. Loading a modified preset visually does not prove portability, correct sample resolution or MIDI playback.
- Report a concrete blocker if no supported control can load the kit. Preserve work; do not claim the kit is complete.
- Finish GUI work with the required completion-summary call when the computer-use surface requires it.
