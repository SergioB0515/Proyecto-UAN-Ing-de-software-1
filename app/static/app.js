(function () {
    'use strict';

    var root = document.documentElement;
    var T = window.APP_I18N || {};

    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

    function guardar(clave, valor) {
        try { localStorage.setItem(clave, valor); } catch (e) {}
    }

    function temaActual() {
        return root.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
    }

    function aplicarTema(tema, comoGuardar) {
        root.setAttribute('data-bs-theme', tema);
        guardar('tema', comoGuardar || tema);
        var meta = qs('meta[name="theme-color"]');
        if (meta) meta.setAttribute('content', tema === 'dark' ? '#0b0d12' : '#f5f6f9');
        qsa('[data-theme-toggle]').forEach(function (b) {
            b.setAttribute('aria-pressed', tema === 'dark' ? 'true' : 'false');
        });
        document.dispatchEvent(new CustomEvent('themechange', { detail: { tema: tema } }));
    }

    var ultimoClic = null;
    document.addEventListener('pointerdown', function (e) { ultimoClic = { x: e.clientX, y: e.clientY }; }, true);

    function alternarTema(e, comoGuardar) {
        var nuevo = temaActual() === 'dark' ? 'light' : 'dark';
        var reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (!document.startViewTransition || reducido) { aplicarTema(nuevo, comoGuardar); return; }
        var origen = (e && e.type === 'click' && ultimoClic) ? ultimoClic : null;
        if (!origen) {
            var b = qs('[data-theme-toggle]');
            var r = b ? b.getBoundingClientRect() : { left: window.innerWidth, top: 0, width: 0, height: 0 };
            origen = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }
        var radio = Math.hypot(Math.max(origen.x, window.innerWidth - origen.x), Math.max(origen.y, window.innerHeight - origen.y));
        var transicion = document.startViewTransition(function () { aplicarTema(nuevo, comoGuardar); });
        transicion.ready.then(function () {
            root.animate({
                clipPath: ['circle(0px at ' + origen.x + 'px ' + origen.y + 'px)', 'circle(' + radio + 'px at ' + origen.x + 'px ' + origen.y + 'px)']
            }, { duration: 550, easing: 'cubic-bezier(.22, 1, .36, 1)', pseudoElement: '::view-transition-new(root)' });
        }).catch(function () {});
    }

    function initTema() {
        qsa('[data-theme-toggle]').forEach(function (b) {
            b.setAttribute('aria-pressed', temaActual() === 'dark' ? 'true' : 'false');
            b.addEventListener('click', alternarTema);
        });
    }

    var ICONO_OJO = '<svg class="icon-eye" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>' +
        '<svg class="icon-eye-off" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 19c-7 0-11-7-11-7a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 7 11 7a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

    function initPassword() {
        qsa('input[type="password"]').forEach(function (input) {
            if (input.closest('.pw-field')) return;
            var envoltura = document.createElement('div');
            envoltura.className = 'pw-field';
            input.parentNode.insertBefore(envoltura, input);
            envoltura.appendChild(input);

            var boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'pw-toggle';
            boton.setAttribute('aria-pressed', 'false');
            boton.setAttribute('aria-label', T.mostrarClave || 'Show password');
            boton.innerHTML = ICONO_OJO;
            boton.addEventListener('click', function () {
                var visible = input.type === 'text';
                input.type = visible ? 'password' : 'text';
                boton.setAttribute('aria-pressed', visible ? 'false' : 'true');
                boton.setAttribute('aria-label', visible ? (T.mostrarClave || 'Show password') : (T.ocultarClave || 'Hide password'));
            });
            envoltura.appendChild(boton);
        });
    }

    var modalConfirmar = null;
    var confirmacionPendiente = null;

    function initConfirmacion() {
        var el = qs('#modalConfirmar');
        if (!el || !window.bootstrap) return;
        modalConfirmar = window.bootstrap.Modal.getOrCreateInstance(el);
        var titulo = qs('[data-confirm-title]', el);
        var cuerpo = qs('[data-confirm-body]', el);
        var aceptar = qs('[data-confirm-accept]', el);

        document.addEventListener('submit', function (e) {
            var form = e.target;
            if (!(form instanceof HTMLFormElement) || form.dataset.confirmado === '1') return;
            var disparador = e.submitter;
            if (!disparador || !disparador.hasAttribute('data-confirm')) return;

            e.preventDefault();
            confirmacionPendiente = { form: form, disparador: disparador };
            titulo.textContent = disparador.textContent.trim() || T.confirmarTitulo || 'Confirm';
            cuerpo.textContent = disparador.getAttribute('data-confirm') || T.confirmarCuerpo || '';
            modalConfirmar.show();
        }, true);

        aceptar.addEventListener('click', function () {
            if (!confirmacionPendiente) return;
            var pendiente = confirmacionPendiente;
            confirmacionPendiente = null;
            modalConfirmar.hide();
            pendiente.form.dataset.confirmado = '1';
            if (pendiente.form.requestSubmit) {
                pendiente.form.requestSubmit(pendiente.disparador);
            } else {
                pendiente.form.submit();
            }
        });

        el.addEventListener('hidden.bs.modal', function () { confirmacionPendiente = null; });
    }

    function initAntiDobleEnvio() {
        document.addEventListener('submit', function (e) {
            var form = e.target;
            if (e.defaultPrevented || !(form instanceof HTMLFormElement)) return;
            if (form.hasAttribute('data-demo') || form.hasAttribute('data-no-lock')) return;
            if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;

            var boton = e.submitter || qs('button[type="submit"], button:not([type])', form);
            if (!boton) return;

            setTimeout(function () {
                qsa('button[type="submit"], button:not([type])', form).forEach(function (b) { b.disabled = true; });
                boton.classList.add('is-loading');
                var spinner = document.createElement('span');
                spinner.className = 'spinner-border spinner-border-sm me-2';
                spinner.setAttribute('aria-hidden', 'true');
                boton.insertBefore(spinner, boton.firstChild);
            }, 0);

            setTimeout(restaurar, 12000);

            function restaurar() {
                qsa('button', form).forEach(function (b) { b.disabled = false; b.classList.remove('is-loading'); });
                qsa('.spinner-border', form).forEach(function (s) { s.remove(); });
                delete form.dataset.confirmado;
            }
        });

        window.addEventListener('pageshow', function (e) {
            if (!e.persisted) return;
            qsa('form button.is-loading').forEach(function (b) {
                b.classList.remove('is-loading');
                var s = qs('.spinner-border', b);
                if (s) s.remove();
            });
            qsa('form button[disabled]').forEach(function (b) { b.disabled = false; });
        });
    }

    var ICONO_LUPA = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>';

    function normalizar(texto) {
        return texto.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    }

    function initFiltroTablas() {
        qsa('.table-card').forEach(function (tarjeta) {
            var tabla = Array.prototype.slice.call(tarjeta.children).filter(function (c) {
                return c.matches('table.table');
            })[0];
            if (!tabla || tabla.hasAttribute('data-no-filter')) return;
            var filas = qsa(':scope > tbody > tr', tabla);
            if (filas.length < 8) return;

            var barra = document.createElement('div');
            barra.className = 'table-tools';
            barra.innerHTML =
                '<div class="table-search">' + ICONO_LUPA.replace('<svg ', '<svg class="ico" ') +
                '<input type="search" class="form-control form-control-sm" autocomplete="off" data-table-search>' +
                '<kbd aria-hidden="true">/</kbd></div>' +
                '<span class="table-count" aria-live="polite"></span>';
            var entrada = qs('input', barra);
            var contador = qs('.table-count', barra);
            entrada.placeholder = T.filtrarTabla || 'Filter this page…';
            entrada.setAttribute('aria-label', T.filtrarTabla || 'Filter this page…');
            tarjeta.insertBefore(barra, tarjeta.firstChild);

            var vacio = document.createElement('div');
            vacio.className = 'table-nomatch';
            vacio.hidden = true;
            vacio.textContent = T.sinCoincidencias || 'No matches.';
            tarjeta.appendChild(vacio);

            var indice = filas.map(function (f) { return normalizar(f.textContent); });

            function actualizar() {
                var q = normalizar(entrada.value.trim());
                var visibles = 0;
                filas.forEach(function (f, i) {
                    var coincide = !q || indice[i].indexOf(q) !== -1;
                    f.hidden = !coincide;
                    if (coincide) visibles++;
                });
                contador.textContent = q ? visibles + ' / ' + filas.length : filas.length + '';
                resaltar(q, filas);
                vacio.hidden = visibles !== 0;
                tabla.hidden = visibles === 0;
            }
            entrada.addEventListener('input', actualizar);
            entrada.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') { entrada.value = ''; actualizar(); entrada.blur(); }
            });
            actualizar();
        });
    }

    function escribiendo(el) {
        if (!el) return false;
        var tag = el.tagName;
        return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
    }

    var esperandoG = false;

    function initAtajos() {
        var ayuda = qs('#modalAtajos');
        var modalAyuda = ayuda && window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(ayuda) : null;

        document.addEventListener('keydown', function (e) {
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            if (escribiendo(e.target)) return;
            if (qs('.modal.show')) return;

            if (esperandoG) {
                esperandoG = false;
                var mapa = { p: 'panel', t: ['tickets', 'capas'], m: 'bandeja', n: 'mas' };
                var objetivo = mapa[e.key];
                if (objetivo) {
                    var lista = [].concat(objetivo);
                    var destino = null;
                    lista.some(function (ico) { destino = qs('.side-link[data-ico="' + ico + '"]'); return !!destino; });
                    if (destino) { e.preventDefault(); window.location.href = destino.href; }
                }
                return;
            }
            if (e.key === 'g') {
                esperandoG = true;
                setTimeout(function () { esperandoG = false; }, 1200);
                return;
            }

            if (e.key === '/') {
                var buscador = qs('[data-table-search], #filtroTextoPalabraClave');
                if (buscador) { e.preventDefault(); buscador.focus(); buscador.select(); }
            } else if (e.key === 'c' && qs('#nuevoComentario')) {
                e.preventDefault();
                var caja = qs('#nuevoComentario');
                caja.scrollIntoView({ block: 'center', behavior: 'smooth' });
                caja.focus({ preventScroll: true });
            } else if (e.key === 'n') {
                var nuevo = qs('[data-shortcut="nuevo"]');
                if (nuevo) { e.preventDefault(); window.location.href = nuevo.href; }
            } else if (e.key === 't') {
                alternarTema();
            } else if (e.key === '[') {
                alternarMenu();
            } else if (e.key === 'j' || e.key === 'k') {
                moverFila(e.key === 'j' ? 1 : -1);
            } else if (e.key === 'Enter' && filaSel && (e.target === document.body || e.target === document.documentElement)) {
                var enlace = qsa('a[href]', filaSel).filter(function (a) { return /\/tickets\/\d+$/.test(a.getAttribute('href')); })[0];
                if (enlace) { e.preventDefault(); window.location.href = enlace.href; }
            } else if (e.key === '?' && modalAyuda) {
                e.preventDefault();
                modalAyuda.show();
            }
        });

        qsa('[data-open-shortcuts]').forEach(function (b) {
            b.addEventListener('click', function () { if (modalAyuda) modalAyuda.show(); });
        });
    }

    function initTextareas() {
        qsa('textarea.form-control').forEach(function (ta) {
            function ajustar() {
                ta.style.height = 'auto';
                ta.style.height = Math.min(ta.scrollHeight + 2, 340) + 'px';
            }
            ta.addEventListener('input', ajustar);
            ta.addEventListener('keydown', function (e) {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    var form = ta.form;
                    if (form && form.checkValidity()) {
                        e.preventDefault();
                        form.requestSubmit ? form.requestSubmit() : form.submit();
                    } else if (form) {
                        form.reportValidity();
                    }
                }
            });
            if (ta.value) ajustar();
        });
    }

    function initAlertas() {
        qsa('.flash-stack .alert').forEach(function (a, i) {
            var espera = a.classList.contains('alert-danger') ? 0 : (a.classList.contains('alert-warning') ? 9000 : 5000);
            if (!espera) return;
            a.setAttribute('data-vida', '');
            a.style.setProperty('--vida', (espera + i * 400) + 'ms');
            setTimeout(function () {
                if (!document.body.contains(a) || !window.bootstrap) return;
                window.bootstrap.Alert.getOrCreateInstance(a).close();
            }, espera + i * 400);
        });
    }

    function initCopiar() {
        qsa('[data-copy]').forEach(function (b) {
            b.addEventListener('click', function () {
                var valor = b.getAttribute('data-copy') || window.location.href;
                var etiqueta = qs('[data-copy-label]', b);
                var original = etiqueta ? etiqueta.textContent : null;

                function listo() {
                    if (!etiqueta) {
                        var previo = b.textContent;
                        b.textContent = '✓ ' + (T.copiado || 'Copied');
                        setTimeout(function () { b.textContent = previo; }, 1400);
                        return;
                    }
                    etiqueta.textContent = T.copiado || 'Copied';
                    setTimeout(function () { etiqueta.textContent = original; }, 1600);
                }

                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(valor).then(listo).catch(function () {});
                } else {
                    var tmp = document.createElement('textarea');
                    tmp.value = valor;
                    document.body.appendChild(tmp);
                    tmp.select();
                    try { document.execCommand('copy'); listo(); } catch (e) {}
                    tmp.remove();
                }
            });
        });
    }

    function initRolArea() {
        var rol = qs('select#rol');
        var contenedor = qs('#area-container');
        if (!rol || !contenedor) return;
        var selector = qs('select', contenedor);

        function sincronizar() {
            var esAgente = rol.value === 'agente';
            contenedor.hidden = !esAgente;
            if (!esAgente && selector) selector.value = '';
        }
        rol.addEventListener('change', sincronizar);
        sincronizar();
    }

    function initNavegacionActual() {
        qsa('.side-link.active, .dropdown-item.active').forEach(function (a) {
            a.setAttribute('aria-current', 'page');
        });
    }


    function etiquetaMenu() {
        var colapsado = root.getAttribute('data-sidebar') === 'colapsado';
        qsa('[data-sidebar-toggle]').forEach(function (b) {
            var texto = colapsado ? (T.expandirMenu || 'Expand menu') : (T.contraerMenu || 'Collapse menu');
            b.setAttribute('aria-label', texto);
            b.setAttribute('title', texto + ' ([)');
            b.setAttribute('aria-expanded', colapsado ? 'false' : 'true');
        });
    }

    function alternarMenu() {
        if (!qs('.sidebar')) return;
        if (window.matchMedia && window.matchMedia('(max-width: 991.98px)').matches) {
            document.body.classList.toggle('menu-abierto');
            return;
        }
        if (root.getAttribute('data-sidebar') === 'colapsado') {
            root.removeAttribute('data-sidebar');
            guardar('menu', 'abierto');
        } else {
            root.setAttribute('data-sidebar', 'colapsado');
            guardar('menu', 'colapsado');
        }
        etiquetaMenu();
    }

    function initMenu() {
        etiquetaMenu();
        qsa('[data-sidebar-toggle]').forEach(function (b) { b.addEventListener('click', alternarMenu); });
        qsa('[data-sidebar-open]').forEach(function (b) {
            b.addEventListener('click', function () { document.body.classList.add('menu-abierto'); });
        });
        qsa('[data-sidebar-close]').forEach(function (b) {
            b.addEventListener('click', function () { document.body.classList.remove('menu-abierto'); });
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') document.body.classList.remove('menu-abierto');
        });
    }

    function escapar(t) {
        return String(t).replace(/[&<>"]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
        });
    }

    function initPaleta() {
        var el = qs('#paleta');
        var datosEl = qs('#paleta-datos');
        if (!el || !datosEl || !window.bootstrap) return;
        var datos = JSON.parse(datosEl.textContent);
        var modal = window.bootstrap.Modal.getOrCreateInstance(el);
        var entrada = qs('.palette-input', el);
        var lista = qs('.palette-list', el);
        var vacio = qs('.palette-empty', el);
        var iconos = {};
        var tpl = qs('#paleta-iconos');
        if (tpl) qsa('[data-i]', tpl.content).forEach(function (s) { iconos[s.getAttribute('data-i')] = s.innerHTML; });

        var visibles = [];
        var activo = 0;

        function resaltar(texto, q) {
            if (!q) return escapar(texto);
            var i = normalizar(texto).indexOf(q);
            if (i < 0) return escapar(texto);
            return escapar(texto.slice(0, i)) + '<mark>' + escapar(texto.slice(i, i + q.length)) + '</mark>' + escapar(texto.slice(i + q.length));
        }

        function filtrar() {
            var bruto = entrada.value.trim();
            var q = normalizar(bruto);
            var palabras = q.split(/\s+/).filter(Boolean);
            var recientes = leerRecientes().map(function (r) {
                return { t: '#' + r.id + ' · ' + r.titulo, u: datos.ticketUrl.replace(/0$/, r.id), g: 'rec', i: 'reciente' };
            });
            visibles = recientes.concat(datos.items).filter(function (it) {
                var n = normalizar(it.t);
                return palabras.every(function (p) { return n.indexOf(p) !== -1; });
            });
            var num = bruto.replace(/^#/, '');
            if (/^\d{1,9}$/.test(num)) {
                visibles.unshift({
                    t: datos.irTicket.replace('__ID__', num),
                    u: datos.ticketUrl.replace(/0$/, num),
                    g: 'tk', i: 'flecha'
                });
            }
            activo = 0;
            pintar(palabras[0] || '');
        }

        function pintar(q) {
            lista.innerHTML = '';
            var grupo = null;
            visibles.forEach(function (it, idx) {
                if (it.g !== grupo) {
                    grupo = it.g;
                    var h = document.createElement('li');
                    h.className = 'palette-group';
                    h.setAttribute('role', 'presentation');
                    h.textContent = datos.grupos[grupo] || '';
                    lista.appendChild(h);
                }
                var li = document.createElement('li');
                li.className = 'palette-item' + (idx === activo ? ' is-active' : '');
                li.setAttribute('role', 'option');
                li.dataset.idx = idx;
                li.innerHTML = '<span class="p-ico">' + (iconos[it.i] || '') + '</span><span>' + resaltar(it.t, q) + '</span><span class="p-hint">↵</span>';
                lista.appendChild(li);
            });
            vacio.hidden = visibles.length !== 0;
        }

        function mover(delta) {
            if (!visibles.length) return;
            activo = (activo + delta + visibles.length) % visibles.length;
            qsa('.palette-item', lista).forEach(function (li) {
                var on = Number(li.dataset.idx) === activo;
                li.classList.toggle('is-active', on);
                if (on) li.scrollIntoView({ block: 'nearest' });
            });
        }

        function ejecutar(it) {
            if (!it) return;
            modal.hide();
            if (it.a === 'tema') { alternarTema(); return; }
            if (it.a === 'atajos') {
                var ayuda = qs('#modalAtajos');
                if (ayuda) setTimeout(function () { window.bootstrap.Modal.getOrCreateInstance(ayuda).show(); }, 200);
                return;
            }
            if (it.u) window.location.href = it.u;
        }

        entrada.addEventListener('input', filtrar);
        entrada.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowDown') { e.preventDefault(); mover(1); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); mover(-1); }
            else if (e.key === 'Enter') { e.preventDefault(); ejecutar(visibles[activo]); }
        });
        lista.addEventListener('click', function (e) {
            var li = e.target.closest('.palette-item');
            if (li) ejecutar(visibles[Number(li.dataset.idx)]);
        });
        lista.addEventListener('mousemove', function (e) {
            var li = e.target.closest('.palette-item');
            if (!li || Number(li.dataset.idx) === activo) return;
            activo = Number(li.dataset.idx);
            qsa('.palette-item', lista).forEach(function (x) { x.classList.toggle('is-active', x === li); });
        });

        el.addEventListener('show.bs.modal', function () { entrada.value = ''; filtrar(); });
        el.addEventListener('shown.bs.modal', function () { entrada.focus(); });

        qsa('[data-palette-open]').forEach(function (b) { b.addEventListener('click', function () { modal.show(); }); });
        document.addEventListener('keydown', function (e) {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
                e.preventDefault();
                if (el.classList.contains('show')) modal.hide(); else modal.show();
            }
        });
    }

    var RANGOS = {
        'alta': 3, 'high': 3, 'media': 2, 'medium': 2, 'baja': 1, 'low': 1,
        'abierto': 1, 'open': 1, 'en progreso': 2, 'in progress': 2, 'cerrado': 3, 'closed': 3
    };

    function claveOrden(celda) {
        var t = (celda ? celda.textContent : '').trim();
        var tl = t.toLowerCase();
        if (Object.prototype.hasOwnProperty.call(RANGOS, tl)) return { n: RANGOS[tl] };
        var f = t.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?/);
        if (f) return { n: new Date(+f[3], +f[2] - 1, +f[1], +(f[4] || 0), +(f[5] || 0)).getTime() };
        var num = t.replace(/^#/, '').replace('%', '').replace(',', '.');
        if (num !== '' && !isNaN(num)) return { n: parseFloat(num) };
        return { s: tl };
    }

    function initOrdenTablas() {
        qsa('.table-card').forEach(function (tarjeta) {
            var tabla = Array.prototype.slice.call(tarjeta.children).filter(function (c) { return c.matches('table.table'); })[0];
            if (!tabla) return;
            var cabeceras = qsa(':scope > thead > tr > th', tabla);
            var cuerpo = qs(':scope > tbody', tabla);
            if (!cabeceras.length || !cuerpo) return;
            var filas = qsa(':scope > tr', cuerpo);
            if (filas.length < 2) return;

            cabeceras.forEach(function (th, col) {
                var muestra = filas[0].children[col];
                if (!th.textContent.trim() || !muestra || qs('form, select, input, button', muestra)) return;
                th.setAttribute('data-sort', '');
                th.setAttribute('tabindex', '0');
                th.setAttribute('title', T.ordenar || 'Sort');
                th.insertAdjacentHTML('beforeend', '<svg class="sort-ind" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 15 6-6 6 6"/></svg>');

                function ordenar() {
                    var asc = th.getAttribute('aria-sort') !== 'ascending';
                    cabeceras.forEach(function (h) { h.removeAttribute('aria-sort'); });
                    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
                    var actuales = qsa(':scope > tr', cuerpo);
                    actuales.sort(function (a, b) {
                        var ka = claveOrden(a.children[col]), kb = claveOrden(b.children[col]);
                        var r;
                        if (ka.n !== undefined && kb.n !== undefined) r = ka.n - kb.n;
                        else r = String(ka.s !== undefined ? ka.s : ka.n).localeCompare(String(kb.s !== undefined ? kb.s : kb.n), undefined, { numeric: true });
                        return asc ? r : -r;
                    });
                    actuales.forEach(function (f) { cuerpo.appendChild(f); });
                }
                th.addEventListener('click', ordenar);
                th.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ordenar(); }
                });
            });
        });
    }

    function initFilasClicables() {
        qsa('.table-card > table.table > tbody > tr').forEach(function (fila) {
            var enlaces = qsa('a[href]', fila).filter(function (a) { return /\/tickets\/\d+$/.test(a.getAttribute('href')); });
            if (enlaces.length !== 1) return;
            var destino = enlaces[0];
            fila.classList.add('is-clickable');
            fila.addEventListener('click', function (e) {
                if (e.target.closest('a, button, input, select, textarea, label, form')) return;
                if (window.getSelection && String(window.getSelection())) return;
                if (e.ctrlKey || e.metaKey) window.open(destino.href, '_blank');
                else window.location.href = destino.href;
            });
        });
    }

    function initCambiosSinGuardar() {
        var sucios = new Set();
        qsa('form').forEach(function (form) {
            if (form.hasAttribute('data-demo') || (form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
            qsa('textarea', form).forEach(function (ta) {
                ta.addEventListener('input', function () {
                    if (ta.value.trim()) sucios.add(form); else sucios.delete(form);
                });
            });
            form.addEventListener('submit', function () { sucios.delete(form); });
        });
        window.addEventListener('beforeunload', function (e) {
            if (!sucios.size) return;
            e.preventDefault();
            e.returnValue = '';
        });
    }

    function initVolverArriba() {
        var boton = qs('[data-to-top]');
        if (!boton) return;
        var visible = false;
        window.addEventListener('scroll', function () {
            var debe = window.scrollY > 700;
            if (debe !== visible) { visible = debe; boton.hidden = !debe; }
        }, { passive: true });
        boton.addEventListener('click', function () { window.scrollTo({ top: 0 }); });
    }


    function initSaludo() {
        var els = qsa('[data-saludo]');
        if (!els.length) return;
        var h = new Date().getHours();
        var saludo = h < 12 ? (T.buenosDias || 'Good morning') : (h < 19 ? (T.buenasTardes || 'Good afternoon') : (T.buenasNoches || 'Good evening'));
        var fecha = '';
        try {
            fecha = new Date().toLocaleDateString(root.getAttribute('lang') || undefined, { weekday: 'long', day: 'numeric', month: 'long' });
        } catch (e) {}
        els.forEach(function (el) {
            var nombre = el.getAttribute('data-nombre');
            el.innerHTML = '<span class="eyebrow-dot"></span><span></span><span class="eyebrow-date"></span>';
            el.children[1].textContent = saludo + (nombre ? ', ' + nombre : '');
            el.children[2].textContent = fecha ? '· ' + fecha : '';
        });
    }

    function initContadores() {
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        qsa('.stat-card .fs-3').forEach(function (el) {
            var objetivo = el.querySelector('a') || el;
            if (objetivo.children.length) return;
            var texto = objetivo.textContent.trim();
            var m = texto.match(/^(\d+(?:\.\d+)?)(%?)$/);
            if (!m) return;
            var final = parseFloat(m[1]);
            var decimales = (m[1].split('.')[1] || '').length;
            var inicio = null;
            var duracion = 900;
            function paso(t) {
                if (inicio === null) inicio = t;
                var p = Math.min(1, (t - inicio) / duracion);
                var e = 1 - Math.pow(1 - p, 3);
                objetivo.textContent = (final * e).toFixed(decimales) + m[2];
                if (p < 1) requestAnimationFrame(paso);
            }
            objetivo.textContent = (0).toFixed(decimales) + m[2];
            requestAnimationFrame(paso);
        });
    }

    function initBrillo() {
        if (window.matchMedia && !window.matchMedia('(hover: hover)').matches) return;
        qsa('.card, .table-card, .tl-body, .composer').forEach(function (el) {
            el.classList.add('fx');
            el.addEventListener('pointermove', function (e) {
                var r = el.getBoundingClientRect();
                el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
                el.style.setProperty('--my', (e.clientY - r.top) + 'px');
            });
        });
    }

    function initProgreso() {
        var barra = qs('.nav-progress');
        if (!barra) return;
        function iniciar() {
            barra.classList.remove('is-loading');
            void barra.offsetWidth;
            barra.classList.add('is-loading');
        }
        document.addEventListener('click', function (e) {
            if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
            var a = e.target.closest('a[href]');
            if (!a || a.target === '_blank' || a.hasAttribute('download') || a.hasAttribute('data-bs-toggle')) return;
            var href = a.getAttribute('href');
            if (!href || href.charAt(0) === '#' || /^(mailto|tel|javascript):/i.test(href)) return;
            if (a.origin !== window.location.origin || /exportar/.test(a.pathname)) return;
            iniciar();
        });
        document.addEventListener('submit', function (e) {
            if (e.defaultPrevented || e.target.hasAttribute('data-demo')) return;
            if (/exportar/.test(e.target.action || '')) return;
            iniciar();
        });
        window.addEventListener('pageshow', function () { barra.classList.remove('is-loading'); });
    }


    var filaSel = null;
    function moverFila(delta) {
        var filas = qsa('.table-card > table.table > tbody > tr.is-clickable').filter(function (f) { return !f.hidden && f.offsetParent !== null; });
        if (!filas.length) return;
        var idx = filaSel ? filas.indexOf(filaSel) : -1;
        idx = Math.max(0, Math.min(filas.length - 1, idx + delta));
        if (filaSel) filaSel.classList.remove('is-selected');
        filaSel = filas[idx];
        filaSel.classList.add('is-selected');
        filaSel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    var desfase = 0;
    (function () {
        var m = qs('meta[name="server-now"]');
        if (!m) return;
        var srv = Date.parse(m.getAttribute('content'));
        if (!isNaN(srv)) desfase = srv - Date.now();
    })();
    function ahora() { return Date.now() + desfase; }

    function parsearFecha(t) {
        var f = (t || '').trim().match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?/);
        if (!f) return null;
        return new Date(+f[3], +f[2] - 1, +f[1], +(f[4] || 0), +(f[5] || 0)).getTime();
    }

    function relativo(ms) {
        var lang = root.getAttribute('lang') || 'es';
        var abs = Math.abs(ms), signo = ms < 0 ? -1 : 1;
        var unidades = [['day', 86400000], ['hour', 3600000], ['minute', 60000]];
        var u = unidades.find(function (x) { return abs >= x[1]; }) || unidades[2];
        var valor = Math.round(abs / u[1]) * signo;
        try { return new Intl.RelativeTimeFormat(lang, { numeric: 'auto', style: 'short' }).format(valor, u[0]); }
        catch (e) { return ''; }
    }

    function duracion(ms) {
        ms = Math.abs(ms);
        var d = Math.floor(ms / 86400000), h = Math.floor(ms % 86400000 / 3600000), m = Math.floor(ms % 3600000 / 60000);
        if (d) return d + 'd ' + h + 'h';
        if (h) return h + 'h ' + m + 'm';
        return m + 'm';
    }

    function initFechasRelativas() {
        qsa('.table-card > table.table').forEach(function (tabla) {
            var cab = qsa(':scope > thead > tr > th', tabla);
            var col = cab.findIndex(function (th) { return /limite|due|deadline/.test(normalizar(th.textContent)); });
            if (col < 0) return;
            qsa(':scope > tbody > tr', tabla).forEach(function (fila) {
                var celda = fila.children[col];
                if (!celda || qs('.estado-cerrado', fila)) return;
                var t = parsearFecha(celda.textContent);
                if (t === null) return;
                var dif = t - ahora();
                var span = document.createElement('span');
                span.className = 'rel-time' + (dif < 0 ? ' t-danger' : (dif < 86400000 ? ' t-warn' : ''));
                span.textContent = relativo(dif);
                span.title = new Date(t).toLocaleString(root.getAttribute('lang') || undefined);
                celda.appendChild(span);
            });
        });
    }

    function initSla() {
        qsa('[data-sla]').forEach(function (caja) {
            var inicio = Date.parse(caja.getAttribute('data-inicio'));
            var limite = Date.parse(caja.getAttribute('data-limite'));
            if (isNaN(inicio) || isNaN(limite) || limite <= inicio) return;
            var texto = qs('[data-sla-texto]', caja);
            var barra = qs('[data-sla-barra]', caja);
            function pintar() {
                var n = ahora();
                var p = Math.max(0, Math.min(100, (n - inicio) / (limite - inicio) * 100));
                var resta = limite - n;
                caja.classList.toggle('t-danger', resta < 0);
                caja.classList.toggle('t-warn', resta >= 0 && p >= 75);
                texto.textContent = resta < 0 ? (T.vencidoHace || 'Overdue by') + ' ' + duracion(resta) : (T.restante || 'Time left') + ': ' + duracion(resta);
                barra.style.setProperty('--p', p);
            }
            requestAnimationFrame(pintar);
            setInterval(pintar, 30000);
        });
    }

    function initBarrasDatos() {
        qsa('.table-card > table.table').forEach(function (tabla) {
            if (qs(':scope > thead', tabla)) return;
            var filas = qsa(':scope > tbody > tr', tabla).filter(function (f) { return f.children.length === 2; });
            var valores = filas.map(function (f) { return parseFloat(f.children[1].textContent); });
            if (!filas.length || valores.some(isNaN)) return;
            var max = Math.max.apply(null, valores) || 1;
            filas.forEach(function (f, i) {
                f.setAttribute('data-bar', '');
                setTimeout(function () { f.style.setProperty('--p', valores[i] / max * 100); }, 120 + i * 60);
            });
        });
    }

    function initEscalonado() {
        qsa('.table-card > table.table > tbody').forEach(function (cuerpo) {
            qsa(':scope > tr', cuerpo).forEach(function (f, i) { f.style.animationDelay = Math.min(i, 24) * 18 + 'ms'; });
        });
    }

    function initTituloNotif() {
        var badge = qs('#notifBadge');
        if (!badge) return;
        var base = document.title.replace(/^\(\d+\+?\)\s*/, '');
        function sync() {
            var n = badge.hidden ? '' : badge.textContent.trim();
            document.title = n ? '(' + n + ') ' + base : base;
        }
        sync();
        new MutationObserver(sync).observe(badge, { attributes: true, childList: true, characterData: true, subtree: true });
    }

    function initTooltipsMenu() {
        var tip = null;
        function quitar() { if (tip) { tip.remove(); tip = null; } }
        qsa('.side-link').forEach(function (a) {
            a.addEventListener('mouseenter', function () {
                if (root.getAttribute('data-sidebar') !== 'colapsado' || window.innerWidth < 992) return;
                quitar();
                var r = a.getBoundingClientRect();
                tip = document.createElement('div');
                tip.className = 'side-tip';
                tip.textContent = a.getAttribute('data-label');
                tip.style.left = (r.right + 10) + 'px';
                tip.style.top = (r.top + r.height / 2) + 'px';
                document.body.appendChild(tip);
            });
            a.addEventListener('mouseleave', quitar);
            a.addEventListener('click', quitar);
        });
    }

    function initConexion() {
        var pila = qs('.flash-stack');
        if (!pila) return;
        var aviso = null;
        function alerta(clase, texto) {
            var d = document.createElement('div');
            d.className = 'alert ' + clase;
            d.setAttribute('role', 'status');
            var ico = document.createElement('span');
            ico.className = 'flash-ico';
            ico.innerHTML = clase.indexOf('success') !== -1
                ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg>'
                : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8.8a15 15 0 0 1 20 0"/><path d="M5 12.6a10 10 0 0 1 14 0"/><path d="M8.5 16.4a5 5 0 0 1 7 0"/><path d="M12 20h.01"/><path d="M3 3l18 18"/></svg>';
            d.appendChild(ico);
            var s = document.createElement('span');
            s.className = 'flash-msg';
            s.textContent = texto;
            d.appendChild(s);
            pila.appendChild(d);
            return d;
        }
        window.addEventListener('offline', function () {
            if (!aviso) aviso = alerta('alert-warning', T.sinConexion || 'Offline');
        });
        window.addEventListener('online', function () {
            if (aviso) { aviso.remove(); aviso = null; }
            var ok = alerta('alert-success', T.conexionOk || 'Back online');
            setTimeout(function () { ok.remove(); }, 3500);
        });
    }


    function leer(clave, defecto) {
        try { var v = localStorage.getItem(clave); return v === null ? defecto : JSON.parse(v); } catch (e) { return defecto; }
    }
    function escribir(clave, valor) {
        try { localStorage.setItem(clave, JSON.stringify(valor)); } catch (e) {}
    }
    function borrar(clave) {
        try { localStorage.removeItem(clave); } catch (e) {}
    }

    function leerRecientes() { return leer('recientes', []).slice(0, 6); }

    function initRecientes() {
        var el = qs('[data-ticket-reciente]');
        if (!el) return;
        var id = el.getAttribute('data-id');
        var lista = leerRecientes().filter(function (r) { return String(r.id) !== String(id); });
        lista.unshift({ id: id, titulo: el.getAttribute('data-titulo') });
        escribir('recientes', lista.slice(0, 6));
    }

    function initBorradores() {
        var hayError = !!qs('.flash-stack .alert-danger');
        qsa('form').forEach(function (form) {
            if (form.hasAttribute('data-demo') || (form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
            qsa('textarea[name]', form).forEach(function (ta) {
                var clave = 'borrador:' + window.location.pathname + ':' + (form.getAttribute('action') || '') + ':' + ta.name;
                var enviado = leer(clave + ':enviado', null);
                if (enviado !== null) {
                    borrar(clave + ':enviado');
                    if (hayError && !ta.value) escribir(clave, enviado);
                }
                var guardado = leer(clave, null);
                if (guardado && !ta.value) {
                    ta.value = guardado;
                    ta.dispatchEvent(new Event('input'));
                    var nota = document.createElement('div');
                    nota.className = 'draft-note';
                    nota.innerHTML = '<span></span><button type="button"></button>';
                    nota.children[0].textContent = T.borradorRestaurado || 'Draft restored';
                    nota.children[1].textContent = T.descartar || 'Discard';
                    nota.children[1].addEventListener('click', function () {
                        ta.value = '';
                        ta.dispatchEvent(new Event('input'));
                        borrar(clave);
                        nota.remove();
                        ta.focus();
                    });
                    var ancla = ta.closest('.composer') || ta;
                    ancla.insertAdjacentElement('afterend', nota);
                }
                var temporizador = null;
                ta.addEventListener('input', function () {
                    clearTimeout(temporizador);
                    temporizador = setTimeout(function () {
                        if (ta.value.trim()) escribir(clave, ta.value); else borrar(clave);
                    }, 350);
                });
                form.addEventListener('submit', function () {
                    clearTimeout(temporizador);
                    if (ta.value.trim()) escribir(clave + ':enviado', ta.value);
                    borrar(clave);
                });
            });
        });
    }

    function initChipsFiltros() {
        var params = new URLSearchParams(window.location.search);
        qsa('.app-main form').forEach(function (form) {
            if ((form.getAttribute('method') || 'get').toLowerCase() !== 'get') return;
            var activos = [];
            qsa('select[name], input[name]', form).forEach(function (campo) {
                var nombre = campo.name;
                var valor = params.get(nombre);
                if (!valor || nombre === 'pagina') return;
                var col = campo.closest('[class*="col"]') || campo.parentElement;
                var etiqueta = col ? qs('.form-label', col) : null;
                var texto = valor;
                if (campo.tagName === 'SELECT') {
                    var opt = Array.prototype.slice.call(campo.options).filter(function (o) { return o.value === valor; })[0];
                    if (opt) texto = opt.textContent.trim();
                }
                var sin = new URLSearchParams(params);
                sin.delete(nombre);
                sin.delete('pagina');
                activos.push({ etiqueta: etiqueta ? etiqueta.textContent.trim() : nombre, texto: texto, url: window.location.pathname + (sin.toString() ? '?' + sin.toString() : '') });
            });
            if (!activos.length) return;
            var cont = document.createElement('div');
            cont.className = 'filter-chips';
            var lab = document.createElement('span');
            lab.className = 'chips-label';
            lab.textContent = (T.filtrosActivos || 'Active filters') + ':';
            cont.appendChild(lab);
            activos.forEach(function (a) {
                var chip = document.createElement('a');
                chip.className = 'chip';
                chip.href = a.url;
                chip.title = T.quitarFiltro || 'Remove filter';
                chip.innerHTML = '<span></span><b></b><span class="chip-x" aria-hidden="true">×</span>';
                chip.children[0].textContent = a.etiqueta + ':';
                chip.children[1].textContent = a.texto;
                cont.appendChild(chip);
            });
            if (activos.length > 1) {
                var limpiar = document.createElement('a');
                limpiar.className = 'chip-clear';
                limpiar.href = window.location.pathname;
                limpiar.textContent = T.limpiarTodo || 'Clear all';
                cont.appendChild(limpiar);
            }
            var contenedor = form.closest('.card') || form;
            contenedor.insertAdjacentElement('afterend', cont);
        });
    }

    function initDensidad() {
        if (leer('densidad', '') === 'compacta') root.setAttribute('data-densidad', 'compacta');
        qsa('.table-tools').forEach(function (barra) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'icon-btn';
            b.title = T.vistaCompacta || 'Compact view';
            b.setAttribute('aria-label', b.title);
            b.setAttribute('aria-pressed', root.getAttribute('data-densidad') === 'compacta' ? 'true' : 'false');
            b.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>';
            b.addEventListener('click', function () {
                var compacta = root.getAttribute('data-densidad') !== 'compacta';
                if (compacta) root.setAttribute('data-densidad', 'compacta'); else root.removeAttribute('data-densidad');
                escribir('densidad', compacta ? 'compacta' : '');
                qsa('.table-tools .icon-btn').forEach(function (x) { x.setAttribute('aria-pressed', compacta ? 'true' : 'false'); });
            });
            barra.appendChild(b);
        });
    }

    function initNotifEscritorio() {
        var pie = qs('[data-notif-escritorio]');
        if (!('Notification' in window)) return;
        if (pie && Notification.permission === 'default') {
            pie.hidden = false;
            qs('button', pie).addEventListener('click', function () {
                Notification.requestPermission().then(function (p) {
                    pie.hidden = true;
                    if (p === 'granted') new Notification('Tickets IT', { body: T.notifActivadas || 'Desktop notifications enabled' });
                });
            });
        }
        document.addEventListener('notif:nueva', function (e) {
            if (Notification.permission !== 'granted' || !document.hidden) return;
            var n = new Notification(T.nuevaNotif || 'Tickets IT', { body: e.detail.texto, tag: 'tickets-it' });
            n.onclick = function () {
                window.focus();
                if (e.detail.ticket) window.location.href = e.detail.ticket;
                n.close();
            };
        });
    }

    function initAyudasClave() {
        qsa('input[type="password"]').forEach(function (input) {
            var cont = input.closest('.pw-field') || input;
            var aviso = null;
            function revisar(e) {
                var activo = e.getModifierState && e.getModifierState('CapsLock');
                if (activo && !aviso) {
                    aviso = document.createElement('div');
                    aviso.className = 'caps-warn';
                    aviso.textContent = '⇪ ' + (T.bloqMayus || 'Caps Lock is on');
                    cont.insertAdjacentElement('afterend', aviso);
                } else if (!activo && aviso) {
                    aviso.remove();
                    aviso = null;
                }
            }
            input.addEventListener('keydown', revisar);
            input.addEventListener('keyup', revisar);
            input.addEventListener('blur', function () { if (aviso) { aviso.remove(); aviso = null; } });

            if (!input.hasAttribute('data-politica')) return;
            var reglas = [/.{8,}/, /[A-Z]/, /[a-z]/, /[0-9]/, /[^A-Za-z0-9]/];
            var ul = document.createElement('ul');
            ul.className = 'pw-rules';
            (T.reglas || ['8+', 'A-Z', 'a-z', '0-9', '#']).forEach(function (texto) {
                var li = document.createElement('li');
                li.textContent = texto;
                ul.appendChild(li);
            });
            var ancla = cont.nextElementSibling && cont.nextElementSibling.classList.contains('caps-warn') ? cont.nextElementSibling : cont;
            ancla.insertAdjacentElement('afterend', ul);
            input.addEventListener('input', function () {
                reglas.forEach(function (r, i) { ul.children[i].classList.toggle('ok', r.test(input.value)); });
            });
        });
    }

    function initContadorTexto() {
        qsa('textarea[data-min-detalle]').forEach(function (ta) {
            var min = parseInt(ta.getAttribute('data-min-detalle'), 10) || 0;
            var fila = document.createElement('div');
            fila.className = 'text-counter';
            fila.innerHTML = '<span class="hint"></span><span class="count"></span>';
            var hint = fila.children[0], cuenta = fila.children[1];
            ta.insertAdjacentElement('afterend', fila);
            function actualizar() {
                var n = ta.value.trim().length;
                cuenta.textContent = n + ' ' + (T.caracteres || 'characters');
                hint.textContent = n > 0 && n < min ? (T.masDetalle || '') : '';
            }
            ta.addEventListener('input', actualizar);
            actualizar();
        });
    }

    function initVistaPreviaFoto() {
        qsa('input[type="file"][name="foto"]').forEach(function (input) {
            input.addEventListener('change', function () {
                var archivo = input.files && input.files[0];
                if (!archivo || !/^image\//.test(archivo.type)) return;
                var tarjeta = input.closest('.card-body') || document;
                var actual = qs('.avatar-perfil, .avatar-iniciales', tarjeta);
                if (!actual) return;
                var lector = new FileReader();
                lector.onload = function () {
                    var img = document.createElement('img');
                    img.className = 'avatar-perfil avatar-preview';
                    img.alt = '';
                    img.src = lector.result;
                    actual.replaceWith(img);
                };
                lector.readAsDataURL(archivo);
            });
        });
    }

    function initImprimir() {
        qsa('[data-imprimir]').forEach(function (b) { b.addEventListener('click', function () { window.print(); }); });
    }


    var soportaResaltado = !!(window.CSS && CSS.highlights && window.Highlight);
    function resaltar(q, filas) {
        if (!soportaResaltado) return;
        CSS.highlights.delete('filtro');
        if (!q || q.length < 2) return;
        var rangos = [];
        filas.forEach(function (f) {
            if (f.hidden) return;
            var walker = document.createTreeWalker(f, NodeFilter.SHOW_TEXT, {
                acceptNode: function (n) { return n.parentElement.closest('select, option, button, form') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
            });
            var nodo;
            while ((nodo = walker.nextNode())) {
                var texto = normalizar(nodo.textContent);
                var i = texto.indexOf(q);
                while (i !== -1) {
                    var r = new Range();
                    r.setStart(nodo, i);
                    r.setEnd(nodo, Math.min(i + q.length, nodo.textContent.length));
                    rangos.push(r);
                    i = texto.indexOf(q, i + q.length);
                }
            }
        });
        if (rangos.length) CSS.highlights.set('filtro', new Highlight(...rangos));
    }

    function preferenciaTema() {
        try { return localStorage.getItem('tema') || 'dark'; } catch (e) { return 'dark'; }
    }

    function initPreferencias() {
        var seg = qs('[data-pref-tema]');
        if (seg) {
            var marcar = function () {
                var actual = preferenciaTema();
                qsa('button', seg).forEach(function (b) { b.classList.toggle('is-on', b.getAttribute('data-valor') === actual); });
            };
            marcar();
            qsa('button', seg).forEach(function (b) {
                b.addEventListener('click', function () {
                    var v = b.getAttribute('data-valor');
                    var real = v === 'sistema' ? (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark') : v;
                    if (real !== temaActual()) alternarTema({ type: 'click' }, v);
                    else { try { localStorage.setItem('tema', v); } catch (e) {} }
                    setTimeout(marcar, 50);
                });
            });
            document.addEventListener('themechange', marcar);
        }
        var dens = qs('[data-pref-densidad]');
        if (dens) {
            dens.checked = root.getAttribute('data-densidad') === 'compacta';
            dens.addEventListener('change', function () {
                if (dens.checked) root.setAttribute('data-densidad', 'compacta'); else root.removeAttribute('data-densidad');
                escribir('densidad', dens.checked ? 'compacta' : '');
            });
        }
        var menu = qs('[data-pref-menu]');
        if (menu) {
            menu.checked = root.getAttribute('data-sidebar') === 'colapsado';
            menu.addEventListener('change', function () {
                if (menu.checked !== (root.getAttribute('data-sidebar') === 'colapsado')) alternarMenu();
            });
        }
        var limpiar = qs('[data-pref-limpiar-recientes]');
        if (limpiar) {
            limpiar.addEventListener('click', function () {
                borrar('recientes');
                var previo = limpiar.textContent;
                limpiar.textContent = '✓';
                setTimeout(function () { limpiar.textContent = previo; }, 1200);
            });
        }
    }

    function initRecordarEmail() {
        var check = qs('[data-recordar-email]');
        var email = qs('#email');
        if (!check || !email) return;
        var guardado = leer('email-recordado', '');
        if (guardado) {
            email.value = guardado;
            check.checked = true;
            var clave = qs('#contrasena');
            if (clave) clave.focus();
        }
        check.form.addEventListener('submit', function () {
            if (check.checked && email.value) escribir('email-recordado', email.value.trim());
            else borrar('email-recordado');
        });
    }


    function initOtp() {
        qsa('input[data-otp]').forEach(function (input) {
            input.addEventListener('input', function () {
                var v = input.value;
                if (/^[\d\s-]+$/.test(v)) {
                    var limpio = v.replace(/\D/g, '').slice(0, 6);
                    if (limpio !== v) input.value = limpio;
                    if (limpio.length === 6 && input.form && input.form.hasAttribute('data-otp-form')) {
                        input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit();
                    }
                } else {
                    input.value = v.toUpperCase();
                }
            });
            input.addEventListener('paste', function () { setTimeout(function () { input.dispatchEvent(new Event('input')); }, 0); });
        });
    }

    function initConfirmacionClave() {
        qsa('input[data-confirma]').forEach(function (conf) {
            var original = document.getElementById(conf.getAttribute('data-confirma'));
            if (!original) return;
            function validar() {
                conf.setCustomValidity(conf.value && conf.value !== original.value ? (T.noCoinciden || 'Passwords do not match') : '');
            }
            conf.addEventListener('input', validar);
            original.addEventListener('input', validar);
        });
    }

    function initDescargaCodigos() {
        qsa('[data-descargar-codigos]').forEach(function (b) {
            b.addEventListener('click', function () {
                var codigos = qsa('[data-codigos] li').map(function (li) { return li.textContent.trim(); });
                var texto = 'Tickets IT\n' + (T.codigosRespaldo || 'Backup codes') + '\n' + new Date().toLocaleString() + '\n\n' + codigos.join('\n') + '\n';
                var url = URL.createObjectURL(new Blob([texto], { type: 'text/plain' }));
                var a = document.createElement('a');
                a.href = url;
                a.download = 'tickets-it-codigos-respaldo.txt';
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTema();
        initMenu();
        initPaleta();
        initPassword();
        initConfirmacion();
        initAntiDobleEnvio();
        initFiltroTablas();
        initAtajos();
        initTextareas();
        initAlertas();
        initCopiar();
        initRolArea();
        initNavegacionActual();
        initOrdenTablas();
        initFilasClicables();
        initVolverArriba();
        initSaludo();
        initContadores();
        initBrillo();
        initProgreso();
        initFechasRelativas();
        initSla();
        initBarrasDatos();
        initEscalonado();
        initTituloNotif();
        initTooltipsMenu();
        initConexion();
        initRecientes();
        initBorradores();
        initChipsFiltros();
        initDensidad();
        initNotifEscritorio();
        initAyudasClave();
        initContadorTexto();
        initVistaPreviaFoto();
        initImprimir();
        initPreferencias();
        initRecordarEmail();
        initOtp();
        initConfirmacionClave();
        initDescargaCodigos();
    });
})();
