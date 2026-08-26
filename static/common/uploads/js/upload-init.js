/**
 * Upload widget wiring for DaTe Website (direct Uppy mode + classic mode).
 *
 * Expected DOM (rendered by core.upload_widgets.DirectUploadWidget):
 *
 * Direct mode:
 *
 *   <div class="django-uppy-widget" data-uppy-widget="1" data-uppy-mode="direct"
 *        data-uppy-scope="..." data-uppy-bucket="..." data-uppy-multi="true|false"
 *        data-uppy-compress="true|false" data-uppy-name="..." ...>
 *     <div data-uppy-mount="1"></div>
 *     <ul class="django-uppy-files" data-uppy-uploaded="1"></ul>
 *   </div>
 *   <input type="hidden" name="..." value="...">
 *
 * On upload completion the JSON payload [{key, name, size}, ...] is written
 * into the sibling hidden input; the Django form parses it on submit. The
 * payload is updated on success and removal, and the form is blocked while
 * uploads are pending or failed. The "uploaded" list is rehydrated from the
 * hidden input on load, so already-uploaded temp files stay visible and
 * removable across reloads and validation errors.
 *
 * Classic mode (direct uploads disabled):
 *
 *   <div class="django-uppy-widget" data-uppy-widget="1" data-uppy-mode="classic">
 *     <input type="file" ...>
 *     <ul class="django-uppy-files" data-uppy-selected="1"></ul>
 *   </div>
 *
 * The selected-file list is kept in sync with the input through a DataTransfer
 * object so the browser submits exactly the files still listed.
 *
 * The signing endpoint (POST /_uploads/sign/) enforces auth, extension
 * allowlist and size caps server-side; the restrictions below are UX only.
 */
(function () {
  'use strict';

  var SIGN_URL = '/_uploads/sign/';

  function csrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  // Size compression and upload concurrency to the device: strong machines
  // run near full speed, weak ones (craptops, old phones) stay gentle so a
  // tab does not run out of memory or hammer the signing endpoint.
  function deviceMemoryGB() {
    var mem = navigator.deviceMemory;
    var cores = navigator.hardwareConcurrency || 1;
    if (mem === undefined) {
      // Safari and Firefox do not expose deviceMemory; fall back on cores.
      mem = cores >= 8 ? 8 : cores >= 4 ? 4 : 2;
    }
    return mem;
  }

  function compressionLimit() {
    var mem = deviceMemoryGB();
    var cores = navigator.hardwareConcurrency || 1;
    // Each concurrent decode of a large photo can need roughly 1/3 GB.
    return Math.max(1, Math.min(cores, Math.floor(mem / 3)));
  }

  function uploadLimit() {
    // Uploads are streamed, not buffered; strong devices may run unlimited.
    return deviceMemoryGB() >= 4 ? Infinity : 3;
  }

  function formatSize(bytes) {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024) return bytes + ' B';
    var units = ['KB', 'MB', 'GB'];
    var i = -1;
    do {
      bytes /= 1024;
      i += 1;
    } while (bytes >= 1024 && i < units.length - 1);
    return bytes.toFixed(1) + ' ' + units[i];
  }

  function parsePayload(raw) {
    try {
      var parsed = JSON.parse(raw || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function signFile(uppy, file, options) {
    var body = new URLSearchParams();
    body.append('scope', options.scope);
    body.append('bucket', options.bucket);
    body.append('name', file.name);
    body.append('size', String(file.size));

    return fetch(SIGN_URL, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: body,
      credentials: 'same-origin',
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) {
          throw new Error(data.error || 'Signing failed');
        }
        file.meta.uploadKey = data.key;
        return { method: data.method, url: data.url, fields: {}, headers: {} };
      });
    });
  }

  function fileRow(file) {
    var li = document.createElement('li');
    li.className = 'django-uppy-file';
    var name = document.createElement('span');
    name.className = 'django-uppy-name';
    name.textContent = file.name;
    var size = document.createElement('span');
    size.className = 'django-uppy-size';
    size.textContent = formatSize(file.size);
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'django-uppy-remove';
    button.textContent = '\u00d7';
    button.setAttribute('aria-label', 'Ta bort ' + file.name);
    li.appendChild(name);
    li.appendChild(size);
    li.appendChild(button);
    return li;
  }

  function initDirect(root) {
    var form = root.closest('form');
    var name = root.dataset.uppyName;
    if (!form || !name || typeof window.Uppy === 'undefined') return;

    var hidden = form.elements[name];
    if (!hidden) return;

    var mount = root.querySelector('[data-uppy-mount]');
    var uploadedList = root.querySelector('[data-uppy-uploaded]');
    if (!mount || !uploadedList) return;

    var options = {
      scope: root.dataset.uppyScope || 'admin',
      bucket: root.dataset.uppyBucket || 'private',
      multi: root.dataset.uppyMulti !== 'false',
      compress: root.dataset.uppyCompress === 'true',
    };

    var maxBytes = parseInt(root.dataset.uppyMaxBytes || '0', 10) || null;
    var allowedExtensions = (root.dataset.uppyAllowedExtensions || '')
      .split(',')
      .filter(Boolean)
      .map(function (ext) {
        return '.' + ext.trim();
      });

    var Core = window.Uppy.Uppy || window.Uppy;
    var uppy = new Core({
      autoProceed: true,
      limit: uploadLimit(),
      restrictions: {
        maxFileSize: maxBytes,
        allowedFileTypes: allowedExtensions.length ? allowedExtensions : null,
        maxNumberOfFiles: options.multi ? null : 1,
      },
    });

    if (options.compress) {
      // Matches the server-side behaviour gallery photos used to apply:
      // downscale to 1600px wide, JPEG quality 60, before upload.
      uppy.use(window.Uppy.Compressor, {
        quality: 0.6,
        maxWidth: 1600,
        limit: compressionLimit(),
        compressorOptions: {
          convertTypes: [],
        },
      });
    }

    uppy.use(window.Uppy.AwsS3, {
      shouldUseMultipart: false,
      getUploadParameters: function (file) {
        return signFile(uppy, file, options);
      },
    });

    uppy.use(window.Uppy.Dashboard, {
      inline: true,
      target: mount,
      height: options.multi ? 300 : 200,
      hideUploadButton: true,
      proudlyDisplayPoweredByUppy: false,
      showProgressDetails: true,
    });

    var uploaded = parsePayload(hidden.value);
    var pendingIds = new Set();
    var failedIds = new Set();
    var submitting = false;

    function submitButtons() {
      return form.querySelectorAll('button[type="submit"], input[type="submit"]');
    }

    function setSubmittable(enabled) {
      submitButtons().forEach(function (button) {
        button.disabled = !enabled;
      });
    }

    function refresh() {
      setSubmittable(pendingIds.size === 0 && failedIds.size === 0);
    }

    function renderUploaded() {
      uploadedList.textContent = '';
      uploaded.forEach(function (entry) {
        if (!entry || typeof entry !== 'object') return;
        var li = fileRow(entry);
        var button = li.querySelector('.django-uppy-remove');
        button.dataset.uppyRemoveKey = entry.key;
        li.dataset.uppyKey = entry.key;
        uploadedList.appendChild(li);
      });
    }

    function writePayload() {
      hidden.value = JSON.stringify(uploaded);
      renderUploaded();
    }

    function removeByKey(key) {
      uploaded = uploaded.filter(function (entry) {
        return entry.key !== key;
      });
      // Best effort: drop the matching in-dashboard file (if any) too.
      uppy.getFiles().forEach(function (file) {
        if (file.meta && file.meta.uploadKey === key) {
          uppy.removeFile(file.id);
        }
      });
      writePayload();
    }

    function showStatus(message) {
      var status = root.querySelector('.django-uppy-status');
      if (!status) {
        status = document.createElement('div');
        status.className = 'django-uppy-status';
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');
        root.appendChild(status);
      }
      status.textContent = message;
    }

    function payloadEntry(file) {
      return {
        key: file.meta.uploadKey,
        name: file.name,
        size: file.size,
      };
    }

    uploadedList.addEventListener('click', function (event) {
      var button = event.target.closest('[data-uppy-remove-key]');
      if (!button) return;
      removeByKey(button.dataset.uppyRemoveKey);
    });

    uppy.on('file-added', function (file) {
      pendingIds.add(file.id);
      showStatus('');
      refresh();
    });

    uppy.on('upload-success', function (file) {
      pendingIds.delete(file.id);
      failedIds.delete(file.id);
      if (file.meta && file.meta.uploadKey) {
        uploaded = uploaded.filter(function (entry) {
          return entry.key !== file.meta.uploadKey;
        });
        uploaded.push(payloadEntry(file));
        writePayload();
      }
      refresh();
    });

    uppy.on('upload-error', function (file) {
      pendingIds.delete(file.id);
      failedIds.add(file.id);
      showStatus('En fil kunde inte laddas upp. Ta bort den eller försök igen innan du sparar.');
      refresh();
    });

    uppy.on('file-removed', function (file) {
      pendingIds.delete(file.id);
      failedIds.delete(file.id);
      if (file.meta && file.meta.uploadKey) {
        uploaded = uploaded.filter(function (entry) {
          return entry.key !== file.meta.uploadKey;
        });
        writePayload();
      }
      refresh();
    });

    uppy.on('complete', function (result) {
      result.successful.forEach(function (file) {
        failedIds.delete(file.id);
        if (file.meta && file.meta.uploadKey) {
          uploaded = uploaded.filter(function (entry) {
            return entry.key !== file.meta.uploadKey;
          });
          uploaded.push(payloadEntry(file));
        }
      });
      result.failed.forEach(function (file) {
        failedIds.add(file.id);
      });
      writePayload();
      refresh();
      if (failedIds.size > 0) {
        showStatus('Vissa filer kunde inte laddas upp. Ta bort dem eller försök igen innan du sparar.');
      }
    });

    form.addEventListener('submit', function (event) {
      if (submitting || pendingIds.size > 0 || failedIds.size > 0) {
        event.preventDefault();
        if (!submitting) {
          showStatus('Vänta tills uppladdningen är klar, eller åtgärda fel innan du sparar.');
        }
        return;
      }
      submitting = true;
      setSubmittable(false);
    });

    renderUploaded();
  }

  function initClassic(root) {
    var input = root.querySelector('input[type="file"]');
    var list = root.querySelector('[data-uppy-selected]');
    if (!input || !list) return;

    function renderSelected() {
      list.textContent = '';
      Array.prototype.forEach.call(input.files, function (file, index) {
        var li = fileRow(file);
        var button = li.querySelector('.django-uppy-remove');
        button.dataset.uppyRemoveIndex = String(index);
        list.appendChild(li);
      });
    }

    list.addEventListener('click', function (event) {
      var button = event.target.closest('[data-uppy-remove-index]');
      if (!button || typeof window.DataTransfer === 'undefined') return;
      var index = parseInt(button.dataset.uppyRemoveIndex, 10);
      if (Number.isNaN(index)) return;
      var dt = new DataTransfer();
      Array.prototype.forEach.call(input.files, function (file, i) {
        if (i !== index) dt.items.add(file);
      });
      input.files = dt.files;
      renderSelected();
    });

    input.addEventListener('change', renderSelected);
    renderSelected();
  }

  function initWidget(root) {
    if (root.dataset.uppyMode === 'classic') {
      initClassic(root);
    } else {
      initDirect(root);
    }
  }

  function init() {
    var widgets = document.querySelectorAll('[data-uppy-widget]');
    for (var i = 0; i < widgets.length; i++) {
      initWidget(widgets[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
