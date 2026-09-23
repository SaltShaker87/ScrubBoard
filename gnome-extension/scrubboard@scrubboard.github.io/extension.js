// Scrubboard GNOME Shell extension (GNOME 45+).
//
// GNOME on Wayland lets only the compositor watch the clipboard, so this
// extension watches it and asks the local Scrubboard daemon (over a 0600 Unix
// socket in $XDG_RUNTIME_DIR) to redact the text. If the daemon isn't running,
// the clipboard is left untouched.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const OWN_PREFIX = '[Scrubboard:';
const PASSWORD_HINT = 'x-kde-passwordManagerHint';

export default class ScrubboardExtension extends Extension {
    enable() {
        this._clipboard = St.Clipboard.get_default();
        this._selection = global.display.get_selection();
        this._ownTexts = new Set();
        this._generation = 0;
        this._handlerId = this._selection.connect('owner-changed', (_sel, type) => {
            if (type === Meta.SelectionType.SELECTION_CLIPBOARD)
                this._onClipboardChanged();
        });
    }

    disable() {
        if (this._handlerId)
            this._selection.disconnect(this._handlerId);
        this._handlerId = 0;
        this._selection = null;
        this._clipboard = null;
        this._ownTexts = null;
    }

    _onClipboardChanged() {
        const mimetypes = this._clipboard.get_mimetypes(St.ClipboardType.CLIPBOARD);
        if (mimetypes.includes(PASSWORD_HINT))
            return; // password manager content is never read
        this._clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clip, text) => {
            if (!text || !this._clipboard)
                return;
            if (this._ownTexts.has(text)) {
                this._ownTexts.delete(text);
                return;
            }
            if (text.startsWith(OWN_PREFIX))
                return;
            const generation = ++this._generation;
            const app = global.display.focus_window?.get_wm_class() ?? null;
            this._redact(text, app, generation);
        });
    }

    _setClipboard(text) {
        this._ownTexts.add(text);
        this._clipboard.set_text(St.ClipboardType.CLIPBOARD, text);
    }

    _redact(text, app, generation) {
        const path = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'scrubboard.sock']);
        const client = new Gio.SocketClient();
        client.connect_async(new Gio.UnixSocketAddress({path}), null, (c, res) => {
            let conn;
            try {
                conn = c.connect_finish(res);
            } catch (_e) {
                return; // daemon not running: leave the clipboard alone
            }
            const request = `${JSON.stringify({text, source_app: app})}\n`;
            try {
                conn.get_output_stream().write_all(new TextEncoder().encode(request), null);
            } catch (_e) {
                conn.close(null);
                return;
            }
            const input = new Gio.DataInputStream({base_stream: conn.get_input_stream()});
            this._readReply(input, conn, generation, null);
        });
    }

    _readReply(input, conn, generation, placeholder) {
        input.read_line_async(GLib.PRIORITY_DEFAULT, null, (stream, res) => {
            let line = null;
            try {
                [line] = stream.read_line_finish_utf8(res);
            } catch (_e) {}
            let msg = null;
            try {
                msg = line ? JSON.parse(line) : null;
            } catch (_e) {}
            if (!msg || !this._clipboard) {
                conn.close(null);
                return;
            }
            if (msg.status === 'accepted') {
                if (generation === this._generation)
                    this._setClipboard(msg.placeholder);
                this._readReply(input, conn, generation, msg.placeholder);
                return;
            }
            conn.close(null);
            if (msg.status !== 'done' || generation !== this._generation)
                return; // skipped, or superseded by a newer copy
            this._clipboard.get_text(St.ClipboardType.CLIPBOARD, (_c, current) => {
                if (current === placeholder)
                    this._setClipboard(msg.text);
            });
        });
    }
}
