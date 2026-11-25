# Estuary list icons

This optional, local skin modification displays station logos in place of
watched-status icons in Antik TV's live listing and archive search results.
It also hides status icons in the programme list for an individual archive day.
The live listing was tested with Estuary on Kodi 22 for Windows; the archive
search extension still needs visual verification. This modification is not
part of the add-on installation.

Estuary's list views use `ListWatchedIconVar` for the small image beside each
item, rather than the item's icon. The following change gives the item icon
priority in the Antik live listing and archive search. It does not change
programme artwork or fanart. Other listings and the parent-folder item retain
Estuary's original behaviour. When the add-on supplies no icon, the original
rules apply; archive search uses its search icon if no station logo is found.

## Apply the modification

1. Close Kodi.
2. Find Estuary's `xml\Variables.xml`. For a standard Windows installation,
   this is `C:\Program Files\Kodi\addons\skin.estuary\xml\Variables.xml`.
   The location may differ for other installations.
3. Back up `Variables.xml` before editing. Editing under `Program Files`
   requires administrator permission.
4. Find `<variable name="ListWatchedIconVar">` and insert these lines immediately
   below it, before the existing `<value>` entries:

   ```xml
   <value condition="String.StartsWith(Container.FolderPath,plugin://plugin.video.antik/) + [String.Contains(Container.FolderPath,action=list_live) | String.Contains(Container.FolderPath,action=search_archive)] + !ListItem.IsParentFolder + !String.IsEmpty(ListItem.Art(icon))">$INFO[ListItem.Art(icon)]</value>
   <value condition="String.StartsWith(Container.FolderPath,plugin://plugin.video.antik/) + String.Contains(Container.FolderPath,action=list_program)"></value>
   ```

5. Save the file, start Kodi and open **Antik TV > Live TV** or search the
   archive. The lists should show station logos beside programmes. The add-on
   must have a local logo or a configured Picons server for each channel.

If you previously applied a version of this modification, replace its existing
Antik entries with the two lines above instead of adding duplicates.

Kodi or skin updates may overwrite this modification, and future versions of
Estuary may use a different layout. If the icons revert after an update, check
the current skin file and reapply the line only if the variable is still
present and the line is missing.

## Remove the modification

Close Kodi and remove the two added `<value>` lines, or restore your backup if it
matches the currently installed Estuary version. Then restart Kodi. Do not
restore an old backup over a newer skin version, as it may undo update changes.
