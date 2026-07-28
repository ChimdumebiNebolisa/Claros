(function (root) {
  'use strict';

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function sameId(left, right) {
    return left != null && right != null && String(left) === String(right);
  }

  function own(object, key) {
    return !!object && Object.prototype.hasOwnProperty.call(object, key);
  }

  function finiteNumber(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function stringId(value) {
    if (value == null) return null;
    var id = String(value);
    return id ? id : null;
  }

  function choiceId(choice) {
    if (!choice || typeof choice !== 'object') return null;
    return stringId(choice.id != null ? choice.id : choice.choice_id);
  }

  function choiceLabel(choice) {
    if (!choice || typeof choice !== 'object') return null;
    var value = choice.text;
    if (value == null) return null;
    var label = String(value).trim();
    return label || null;
  }

  function choicesById(choices) {
    var result = Object.create(null);
    asArray(choices).forEach(function (choice) {
      var id = choiceId(choice);
      if (id && !own(result, id)) result[id] = choice;
    });
    return result;
  }

  function normalizedRegion(raw, page) {
    if (!raw || typeof raw !== 'object') return null;
    var candidate = raw.region || raw.normalized_region || raw.answer_region || raw;
    var x = finiteNumber(candidate.x);
    var y = finiteNumber(candidate.y);
    var width = finiteNumber(candidate.width);
    var height = finiteNumber(candidate.height);
    if (x != null && y != null && width != null && height != null && x >= 0 && y >= 0 && width > 0 && height > 0 && x + width <= 1 && y + height <= 1) {
      return { x: x, y: y, width: width, height: height };
    }

    var bbox = asArray(raw.bbox);
    var pageWidth = page && finiteNumber(page.width_points);
    var pageHeight = page && finiteNumber(page.height_points);
    if (bbox.length !== 4 || !pageWidth || !pageHeight) return null;
    var x0 = finiteNumber(bbox[0]);
    var y0 = finiteNumber(bbox[1]);
    var x1 = finiteNumber(bbox[2]);
    var y1 = finiteNumber(bbox[3]);
    if (x0 == null || y0 == null || x1 == null || y1 == null || x1 <= x0 || y1 <= y0) return null;
    if (x0 < 0 || y0 < 0 || x1 > pageWidth || y1 > pageHeight) return null;
    return {
      x: x0 / pageWidth,
      y: y0 / pageHeight,
      width: (x1 - x0) / pageWidth,
      height: (y1 - y0) / pageHeight
    };
  }

  function isApprovedRegion(region) {
    if (!region || typeof region !== 'object') return false;
    return region.safe_for_write === true || region.safety === 'approved' || region.answer_region_status === 'approved' || region.answer_region_status === 'safe';
  }

  function hasSidePanelFallback(task) {
    return !!task && (task.side_panel_fallback === true || task.answer_region_status === 'side_panel');
  }

  function displayTaskLabel(task) {
    if (!task) return 'task';
    if (task.legacyQuestionId != null) return String(task.legacyQuestionId);
    return String(task.order + 1);
  }

  function displayTargetLabel(target, task) {
    if (!target) return 'response';
    if (target.role === 'explanation') return 'Explanation';
    if (target.role === 'show_work') return 'Show your work';
    if (target.role === 'choice') {
      var label = target.choiceLabel || (
        task && task.choiceById && target.choiceId != null
          ? choiceLabel(task.choiceById[String(target.choiceId)])
          : null
      );
      if (label) return 'Choice ' + label;
      return 'Choice';
    }
    if (task && task.responseTargetIds.length > 1) return 'Response ' + (target.order + 1);
    return 'Answer';
  }

  function findTask(document, taskId) {
    return document && asArray(document.tasks).find(function (task) { return sameId(task.id, taskId); }) || null;
  }

  function findResponseTarget(document, responseRegionId) {
    if (!document || responseRegionId == null) return null;
    return document.responseTargetsById && document.responseTargetsById[String(responseRegionId)] || null;
  }

  function taskTargets(document, task) {
    if (!document || !task) return [];
    return task.responseTargetIds.map(function (id) {
      return findResponseTarget(document, id);
    }).filter(Boolean);
  }

  function targetForTask(document, task, responseTargetId) {
    var target = findResponseTarget(document, responseTargetId);
    return target && task && sameId(target.taskId, task.id) ? target : null;
  }

  function defaultResponseTarget(document, task) {
    if (!document || !task) return null;
    return targetForTask(document, task, task.defaultResponseTargetId) || taskTargets(document, task)[0] || null;
  }

  function sortByOrder(items) {
    return items.slice().sort(function (left, right) {
      var orderDelta = Number(left.order || 0) - Number(right.order || 0);
      return orderDelta || String(left.id).localeCompare(String(right.id));
    });
  }

  function normalizeDocument(input) {
    input = input || {};
    if (input.normalized === true) return input;
    if (input.document && input.document.normalized === true) return input.document;

    var rawDocument = input.document && Array.isArray(input.document.tasks)
      ? input.document
      : (Array.isArray(input.tasks) ? input : null);
    var rawTasks = rawDocument ? asArray(rawDocument.tasks) : asArray(input.questions);
    var pages = rawDocument ? asArray(rawDocument.pages) : asArray(input.pages);
    var pageByIndex = Object.create(null);
    pages.forEach(function (page) {
      if (page && page.page_index != null) pageByIndex[String(page.page_index)] = page;
    });
    var rawRegionsById = Object.create(null);
    if (rawDocument) {
      asArray(rawDocument.response_regions).forEach(function (region) {
        if (region && region.id != null) rawRegionsById[String(region.id)] = region;
      });
    }

    var responseTargetsById = Object.create(null);
    var responseTargets = [];
    var tasks = [];
    var seenTaskIds = Object.create(null);

    function addTarget(task, rawTarget, relation, fallbackId, virtual) {
      var id = rawTarget && rawTarget.id != null
        ? String(rawTarget.id)
        : (relation && relation.response_region_id != null
          ? String(relation.response_region_id)
          : fallbackId);
      if (!id || own(responseTargetsById, id)) return null;
      var pageIndex = finiteNumber(rawTarget && rawTarget.page_index);
      if (pageIndex == null) pageIndex = task.anchorPageIndex;
      var page = pageByIndex[String(pageIndex)] || null;
      var approved = !virtual && isApprovedRegion(rawTarget);
      var region = approved ? normalizedRegion(rawTarget, page) : null;
      var safeForWrite = approved && !!region;
      var useSidePanel = !safeForWrite && task.sidePanelFallback;
      var targetChoiceId = relation && relation.choice_id != null
        ? stringId(relation.choice_id)
        : stringId(rawTarget && rawTarget.choice_id);
      var targetChoice = targetChoiceId && task.choiceById[targetChoiceId];
      var target = {
        id: id,
        taskId: task.id,
        order: finiteNumber(relation && relation.order) != null
          ? finiteNumber(relation.order)
          : (finiteNumber(rawTarget && rawTarget.order) != null ? finiteNumber(rawTarget.order) : task.responseTargetIds.length),
        role: (relation && relation.role) || (rawTarget && rawTarget.role) || 'answer',
        choiceId: targetChoiceId,
        choiceLabel: choiceLabel(targetChoice),
        pageIndex: pageIndex,
        regionType: (rawTarget && rawTarget.region_type) || 'unknown',
        responseType: (rawTarget && rawTarget.response_type) || task.responseType || 'short_text',
        safety: (rawTarget && rawTarget.safety) || (safeForWrite ? 'approved' : 'needs_review'),
        safeForWrite: safeForWrite,
        useSidePanel: useSidePanel,
        canWrite: safeForWrite || useSidePanel,
        region: region,
        virtual: !!virtual
      };
      responseTargetsById[id] = target;
      responseTargets.push(target);
      task.responseTargetIds.push(id);
      return target;
    }

    rawTasks.forEach(function (rawTask, index) {
      if (!rawTask || typeof rawTask !== 'object') return;
      // Flat compatibility projections carry both a numeric display alias
      // (`id`) and the canonical opaque `task_id`; never promote the alias to
      // client identity.
      var rawTaskId = rawDocument
        ? rawTask.id
        : (rawTask.task_id != null ? rawTask.task_id : rawTask.id);
      var taskId = rawTaskId != null ? String(rawTaskId) : ('legacy-task-' + (index + 1));
      if (own(seenTaskIds, taskId)) return;
      seenTaskIds[taskId] = true;
      var legacyQuestionId = rawTask.legacy_question_id != null
        ? rawTask.legacy_question_id
        : (rawDocument ? null : rawTask.id);
      var anchorPageIndex = finiteNumber(rawTask.anchor_page_index);
      if (anchorPageIndex == null) anchorPageIndex = finiteNumber(rawTask.page_index);
      if (anchorPageIndex == null) anchorPageIndex = Math.max(0, (finiteNumber(rawTask.page) || 1) - 1);
      var rawChoices = asArray(rawTask.choices);
      var task = {
        id: taskId,
        legacyQuestionId: legacyQuestionId,
        order: finiteNumber(rawTask.order) != null ? finiteNumber(rawTask.order) : index,
        label: rawTask.label == null ? null : String(rawTask.label),
        promptText: String(rawTask.prompt_text != null ? rawTask.prompt_text : (rawTask.text || '')),
        anchorPageIndex: anchorPageIndex,
        parentTaskId: rawTask.parent_task_id == null ? null : String(rawTask.parent_task_id),
        subpart: rawTask.subpart == null ? null : String(rawTask.subpart),
        choices: rawChoices,
        choiceById: choicesById(rawChoices),
        responseType: rawTask.response_type || 'short_text',
        sidePanelFallback: hasSidePanelFallback(rawTask),
        defaultResponseTargetId: stringId(rawTask.response_target_id),
        responseTargetIds: []
      };

      if (rawDocument) {
        asArray(rawTask.response_links).forEach(function (relation) {
          if (!relation || relation.response_region_id == null) return;
          var rawRegion = rawRegionsById[String(relation.response_region_id)];
          if (rawRegion) addTarget(task, rawRegion, relation, String(relation.response_region_id), false);
        });
        // The client-safe document projection nests response regions under each
        // task so it can omit unapproved geometry. Accept that authoritative
        // view as well as the persisted document's response_links graph.
        if (!task.responseTargetIds.length) {
          asArray(rawTask.response_regions).forEach(function (region, regionIndex) {
            if (!region || typeof region !== 'object') return;
            addTarget(
              task,
              region,
              {
                response_region_id: region.id,
                role: region.role,
                order: region.order,
                choice_id: region.choice_id
              },
              String(region.id != null ? region.id : (task.id + ':response-' + (regionIndex + 1))),
              false
            );
          });
        }
      } else {
        var legacyRegions = asArray(rawTask.response_regions);
        if (legacyRegions.length) {
          legacyRegions.forEach(function (region, regionIndex) {
            if (!region || typeof region !== 'object') return;
            addTarget(
              task,
              region,
              {
                response_region_id: region.id,
                role: region.role,
                order: region.order,
                choice_id: region.choice_id
              },
              String(region.id != null ? region.id : (task.id + ':response-' + (regionIndex + 1))),
              false
            );
          });
        } else if (rawTask.answer_region) {
          addTarget(
            task,
            {
              id: rawTask.response_target_id || (task.id + ':response-1'),
              page_index: anchorPageIndex,
              region: rawTask.answer_region,
              answer_region_status: rawTask.answer_region_status,
              safe_for_write: rawTask.answer_region_status === 'approved' || rawTask.answer_region_status === 'safe'
            },
            { role: 'answer', order: 0 },
            task.id + ':response-1',
            false
          );
        }
      }

      // The canonical client projection may intentionally default a task to
      // its virtual side-panel target even when it also exposes physical
      // targets (for example a choice-only task). Keep that opaque target in
      // client state instead of guessing from response-region order.
      if (
        task.defaultResponseTargetId &&
        !targetForTask({ responseTargetsById: responseTargetsById }, task, task.defaultResponseTargetId) &&
        task.sidePanelFallback &&
        task.defaultResponseTargetId === task.id + ':side-panel'
      ) {
        addTarget(
          task,
          null,
          { role: 'answer', order: task.responseTargetIds.length },
          task.defaultResponseTargetId,
          true
        );
      }

      if (!task.responseTargetIds.length) {
        addTarget(
          task,
          null,
          { role: 'answer', order: 0 },
          task.defaultResponseTargetId || (task.id + ':side-panel'),
          true
        );
      }
      if (!task.defaultResponseTargetId) {
        var fallbackTarget = defaultResponseTarget({ responseTargetsById: responseTargetsById }, task);
        task.defaultResponseTargetId = fallbackTarget ? fallbackTarget.id : null;
      }
      tasks.push(task);
    });

    tasks = sortByOrder(tasks);
    tasks.forEach(function (task) {
      task.responseTargetIds = sortByOrder(taskTargets({ responseTargetsById: responseTargetsById }, task)).map(function (target) {
        return target.id;
      });
    });
    responseTargets = sortByOrder(responseTargets);
    var pageCount = finiteNumber(input.pageCount);
    if (pageCount == null) pageCount = finiteNumber(input.page_count);
    if (pageCount == null) pageCount = pages.length;
    if (pageCount == null || pageCount < 1) {
      pageCount = tasks.reduce(function (maximum, task) {
        return Math.max(maximum, task.anchorPageIndex + 1);
      }, 1);
    }
    return {
      normalized: true,
      schemaVersion: rawDocument && rawDocument.schema_version || 'legacy-adapter-v1',
      pages: pages,
      pageCount: pageCount,
      tasks: tasks,
      responseTargets: responseTargets,
      responseTargetsById: responseTargetsById
    };
  }

  function create(options) {
    var container = options.container;
    var pageImage = options.pageImage;
    var overlayLayer = options.overlayLayer;
    var pageLabel = options.pageLabel;
    var zoomLabel = options.zoomLabel;
    var state = {
      assignmentId: null,
      assignmentCapability: null,
      document: null,
      responseStates: Object.create(null),
      currentPage: 1,
      pageCount: 1,
      activeTaskId: null,
      activeResponseRegionId: null,
      zoom: 100,
    };

    function pageResponseTargets() {
      if (!state.document) return [];
      return state.document.responseTargets.filter(function (target) {
        return target.region && target.pageIndex + 1 === state.currentPage;
      });
    }

    function updateToolbar() {
      if (pageLabel) pageLabel.textContent = 'Page ' + state.currentPage + ' of ' + state.pageCount;
      if (zoomLabel) zoomLabel.textContent = state.zoom + '%';
      container.style.setProperty('--document-zoom', state.zoom + '%');
    }

    function renderOverlays() {
      overlayLayer.replaceChildren();
      pageResponseTargets().forEach(function (target) {
        var task = findTask(state.document, target.taskId);
        if (!task || !target.region) return;
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'answer-region';
        button.dataset.taskId = task.id;
        button.dataset.responseRegionId = target.id;
        button.style.left = (target.region.x * 100) + '%';
        button.style.top = (target.region.y * 100) + '%';
        button.style.width = (target.region.width * 100) + '%';
        button.style.height = (target.region.height * 100) + '%';
        var label = displayTargetLabel(target, task);
        var placement = target.safeForWrite
          ? 'safe answer area'
          : (target.useSidePanel ? 'side panel only; the original page remains unchanged' : 'location needs review; writing is unavailable');
        button.setAttribute('aria-label', 'Question ' + displayTaskLabel(task) + ', ' + label + ', ' + placement);
        button.setAttribute('aria-pressed', String(sameId(state.activeResponseRegionId, target.id)));
        if (sameId(state.activeResponseRegionId, target.id)) button.classList.add('is-active');
        if (!target.safeForWrite) button.classList.add('needs-review');
        var responseState = state.responseStates[String(target.id)] || {};
        var answer = responseState.written || '';
        var number = document.createElement('span');
        number.className = 'region-number';
        number.textContent = 'Q' + displayTaskLabel(task) + (task.responseTargetIds.length > 1 ? ' ' + label : '');
        var answerText = document.createElement('span');
        answerText.className = 'region-answer';
        answerText.textContent = answer;
        button.appendChild(number);
        button.appendChild(answerText);
        button.addEventListener('click', function () {
          state.activeTaskId = task.id;
          state.activeResponseRegionId = target.id;
          renderOverlays();
          if (options.onSelectTarget) options.onSelectTarget(task.id, target.id, target);
          else if (options.onSelectQuestion) options.onSelectQuestion(task);
        });
        overlayLayer.appendChild(button);
      });
    }

    function renderPage() {
      pageImage.alt = 'Original worksheet page ' + state.currentPage;
      var requestUrl = '/api/assignments/' + state.assignmentId + '/pages/' + state.currentPage + '.png';
      fetch(requestUrl, {
        headers: { 'X-Assignment-Capability': state.assignmentCapability || '' }
      }).then(function (response) {
        if (!response.ok) throw new Error('Could not load worksheet page.');
        return response.blob();
      }).then(function (blob) {
        if (state.pageObjectUrl) URL.revokeObjectURL(state.pageObjectUrl);
        state.pageObjectUrl = URL.createObjectURL(blob);
        pageImage.src = state.pageObjectUrl;
      }).catch(function () {
        pageImage.removeAttribute('src');
        if (options.onPageError) options.onPageError();
      });
      updateToolbar();
      renderOverlays();
    }

    function load(data) {
      state.assignmentId = data.assignmentId;
      state.assignmentCapability = data.assignmentCapability || null;
      state.document = normalizeDocument(data.document && data.document.normalized ? data.document : data);
      state.pageCount = Math.max(1, Number(data.pageCount || state.document.pageCount || 1));
      state.currentPage = 1;
      state.responseStates = data.responseStates || Object.create(null);
      var firstTask = state.document.tasks[0] || null;
      state.activeTaskId = data.activeTaskId || (firstTask && firstTask.id) || null;
      var activeTask = findTask(state.document, state.activeTaskId) || firstTask;
      state.activeTaskId = activeTask && activeTask.id || null;
      var activeTarget = targetForTask(state.document, activeTask, data.activeResponseRegionId) || defaultResponseTarget(state.document, activeTask);
      state.activeResponseRegionId = activeTarget && activeTarget.id || null;
      renderPage();
    }

    function setPage(page) {
      state.currentPage = clamp(Number(page), 1, state.pageCount);
      renderPage();
    }

    function setZoom(zoom) {
      state.zoom = clamp(Math.round(Number(zoom)), 75, 175);
      updateToolbar();
    }

    function fitWidth() {
      setZoom(100);
    }

    function setActiveTarget(taskId, responseRegionId) {
      var task = findTask(state.document, taskId);
      var target = findResponseTarget(state.document, responseRegionId);
      if (!task || !target || !sameId(target.taskId, task.id)) return;
      state.activeTaskId = task.id;
      state.activeResponseRegionId = target.id;
      state.currentPage = clamp(target.pageIndex + 1 || task.anchorPageIndex + 1, 1, state.pageCount);
      renderPage();
      var activeRegion = Array.prototype.find.call(overlayLayer.children, function (element) {
        return element.dataset && element.dataset.responseRegionId === String(target.id);
      });
      if (activeRegion) activeRegion.scrollIntoView({ block: 'center', inline: 'center' });
    }

    function setActiveQuestion(questionId) {
      var task = state.document && state.document.tasks.find(function (item) {
        return sameId(item.legacyQuestionId, questionId) || sameId(item.id, questionId);
      });
      var target = defaultResponseTarget(state.document, task);
      if (task && target) setActiveTarget(task.id, target.id);
    }

    function updateResponseState(responseRegionId, responseState) {
      state.responseStates[String(responseRegionId)] = responseState || {};
      renderOverlays();
    }

    function updateAnswer(questionOrResponseId, text) {
      var target = findResponseTarget(state.document, questionOrResponseId);
      if (!target) {
        var task = state.document && state.document.tasks.find(function (item) {
          return sameId(item.legacyQuestionId, questionOrResponseId) || sameId(item.id, questionOrResponseId);
        });
        target = defaultResponseTarget(state.document, task);
      }
      if (!target) return;
      var responseState = state.responseStates[String(target.id)] || {};
      responseState.written = text || '';
      updateResponseState(target.id, responseState);
    }

    return {
      load: load,
      setPage: setPage,
      setZoom: setZoom,
      fitWidth: fitWidth,
      setActiveTarget: setActiveTarget,
      setActiveQuestion: setActiveQuestion,
      updateResponseState: updateResponseState,
      updateAnswer: updateAnswer,
      getState: function () { return state; }
    };
  }

  root.ClarosWorksheetView = {
    create: create,
    normalizeDocument: normalizeDocument,
    findTask: findTask,
    findResponseTarget: findResponseTarget,
    taskTargets: taskTargets,
    defaultResponseTarget: defaultResponseTarget,
    displayTaskLabel: displayTaskLabel,
    displayTargetLabel: displayTargetLabel
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.ClarosWorksheetView;
})(typeof window !== 'undefined' ? window : this);
