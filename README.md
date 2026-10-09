# Lodestone Locales

The translations for every [Lodestone](https://lode.gg) plugin. Servers download these
files on startup, so a fix merged here reaches every server on its next restart or
reload, with no plugin update needed.

Spotted a typo, a clumsy phrase, or a language that's missing? Open a pull request.

## Layout

One folder per project, one file per language. A project with a proxy plugin keeps its
locales in a `Velocity` folder inside its own:

```
Barrier/
  manifest.json   which languages the folder has
  en_us.json      English, the source every other file is checked against
  fr_fr.json
  ...
Bookshelf/
  en_us.json ...
  Velocity/
    en_us.json ...
```

Every file is a flat JSON object of key to text:

```json
{
  "barrier.config.saved": "<green>Paramètres de Barrier enregistrés.",
  "locale.display_name": "Français"
}
```

## Fixing a translation

Edit the value in that language's file and open a pull request. Keep the key as it is.

## Adding a language

1. Copy the plugin's `en_us.json` to your locale code, lowercase, e.g. `sv_se.json`.
2. Set `locale.display_name` to the language's own name (`Svenska`) and
   `locale.sort_order` to a number, which decides where it sits in the language picker.
3. Translate the values. Keys you leave out are shown in English, so a partial file is fine.
4. Run `python3 scripts/validate.py --fix` to add it to `manifest.json`.

## Rules

A check runs on every pull request and fails, pointing at the line, if any of these is
broken:

- **Keep every tag exactly.** Anything in angle brackets stays as it is, the same number of
  times. That covers colours and formatting (`<red>`, `<bold>`, `<reset>`) and
  placeholders the plugin fills in (`<player>`, `<time>`, `<size>`). Don't translate inside
  them. You can move them around to suit your grammar.
- **Keep every `%s`, line break, and the spaces** at the start and end of the English text.
- **Don't translate commands** (`/worldborder set height <value>`) or product names
  (Barrier, Lodestone, VulkanMod). A few phrases players have to type, like
  `"I understand"` in Bookshelf, also stay in English.
- **Only keys that exist in `en_us.json`**, with no key twice and no empty values.
  Leave a key out instead and it shows in English.
- **Format the file** with `python3 scripts/validate.py --fix` (keys sorted, 2-space
  indent, UTF-8 without BOM). The same command adds a new language to `manifest.json`.

Contributions change language files, manifests and this README. The English files and
the checks themselves are maintained alongside the plugins, so for those, open an issue.
Every pull request is reviewed before it's merged.

Run the check yourself before opening the pull request:

```
python3 scripts/validate.py
```

## For server owners

Your own edits always win. Barrier, for example, keeps its locale files in
`plugins/Barrier/locales/`: change any text there and your version is used instead of
the one from this repository. Text you haven't touched keeps following this repository,
so fixes still reach you.
