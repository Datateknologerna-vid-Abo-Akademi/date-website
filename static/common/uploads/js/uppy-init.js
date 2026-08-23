/**
 * Uppy direct-to-storage upload wiring for DaTe Website.
 *
 * Expected DOM (rendered by core.upload_widgets.DirectUploadWidget):
 *
 *   <div class="django-uppy-widget" data-uppy-widget="1" data-uppy-scope="..."
 *        data-uppy-bucket="..." data-uppy-multi="true|false"
 *        data-uppy-compress="true|false" data-uppy-name="..." ...></div>
 *   <input type="hidden" name="..." value="...">
 *
 * On upload completion the JSON payload [{key, name, size}, ...] is written
 * into the sibling hidden input; the Django form parses it on submit. The
 * payload is updated on success and removal, and the form is blocked while
 * uploads are pending or failed.
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

  function signFile(uppy, file, options) {
    var body = new URLSearchParams();
    body.append('scope', options.scope);
    body.append('bucket', options.bucket);
    body.append('name', file.name);
    body.append('size', String(file.size));
    body.append('type', file.type || '');

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

  function initWidget(root) {
    var form = root.closest('form');
    var name = root.dataset.uppyName;
    if (!form || !name) return;

    var hidden = form.querySelector('input[name="' + name + '"]');
    if (!hidden) return;

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

    var Core = Uppy.Core || Uppy;
    var uppy = new Core({
      autoProceed: true,
      restrictions: {
        maxFileSize: maxBytes,
        allowedFileTypes: allowedExtensions.length ? allowedExtensions : null,
        maxNumberOfFiles: options.multi ? null : 1,
      },
    });

    if (options.compress) {
      // Matches the server-side behaviour gallery photos used to apply:
      // downscale to 1600px wide, JPEG quality 60, before upload.
      uppy.use(Uppy.Compressor, {
        quality: 0.6,
        maxWidth: 1600,
      });
    }

    uppy.use(Uppy.AwsS3, {
      shouldUseMultipart: false,
      getUploadParameters: function (file) {
        return signFile(uppy, file, options);
      },
    });

    uppy.use(Uppy.Dashboard, {
      inline: true,
      target: root,
      height: options.multi ? 300 : 200,
      hideUploadButton: true,
      proudlyDisplayPoweredByUppy: false,
      showProgressDetails: true,
    });

    var uploaded = [];
    var pendingIds = new Set();
    var failedIds = new Set();

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

    function writePayload() {
      hidden.value = JSON.stringify(uploaded);
    }

    function showStatus(message) {
      var status = root.querySelector('.django-uppy-status');
      if (!status) {
        status = document.createElement('div');
        status.className = 'django-uppy-status';
        root.appendChild(status);
      }
      status.textContent = message;
    }

    function payloadEntry(file) {
      return {
        key: file.meta.uploadKey,
        name: file.name,
        size: file.size,
        type: file.type || '',
      };
    }

    uppy.on('file-added', function (file) {
      pendingIds.add(file.id);
      showStatus('');
      refresh();
    });

    uppy.on('upload-success', function (file) {
      pendingIds.delete(file.id);
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
      // Safety net: rebuild the payload from what actually succeeded, in case
      // retries or removals left it stale.
      uploaded = result.successful
        .filter(function (file) {
          return file.meta && file.meta.uploadKey;
        })
        .map(payloadEntry);
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
      if (pendingIds.size > 0 || failedIds.size > 0) {
        event.preventDefault();
        showStatus('Vänta tills uppladdningen är klar, eller åtgärda fel innan du sparar.');
      }
    });
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
