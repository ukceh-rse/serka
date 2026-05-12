document.addEventListener("alpine:init", () => {
  Alpine.data("app", () => ({
    query: "",
    results: [],
    answer: {
      show: false,
      raw: "",
      content: "",
      complete: false,
    },
    agentStatus: {
      show: false,
      message: "",
    },
    aiEnabled: false,
    thinking: false,
    splash: true,
    hasSearched: false,
    showAiTooltip: false,
    modal: {
      show: false,
      item: "",
      type: "",
      text: "",
      onDone: null,
    },
    toast: {
      show: false,
      title: "Toast Title",
      msg: "Toast Message",
    },
    privacyNotice: {
      show: true,
      accepted: false,
    },
    async typeQuery(text) {
      this.query = "";
      for (const char of text) {
        this.query += char;
        await new Promise(r => setTimeout(r, 45));
      }
      this.aiEnabled = true;
      this.search();
    },
    async search() {
      this.splash = false;
      this.results = [];
      this.answer = { content: "", complete: false, show: false, raw: "" };
      this.agentStatus = { show: false, message: "" };
      this.thinking = true;
      if (this.aiEnabled) this.streamingChat();
      try {
        const response = await fetch(`/v1/query/semantic?q=${this.query}`);
        const flat = await response.json();
        this.results = this.groupResults(flat);
        if (!this.hasSearched) {
          this.hasSearched = true;
          if (!this.aiEnabled) {
            this.showAiTooltip = true;
            setTimeout(() => { this.showAiTooltip = false; }, 5000);
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        this.thinking = false;
      }
    },
    async streamingChat() {
      this.agentStatus = { show: true, message: "Thinking..." };
      try {
        const response = await fetch("/v1/chat/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({ message: this.query }),
        });
        if (!response.ok) {
          console.error("Chat stream error:", response.status);
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          sseBuffer += decoder.decode(value, { stream: true });
          const lines = sseBuffer.split("\n");
          sseBuffer = lines.pop();
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const event = JSON.parse(line.slice(6));
            switch (event.type) {
              case "TOOL_CALL_START":
                this.agentStatus = {
                  show: true,
                  message: `Using tool: ${event.toolCallName}…`,
                };
                break;
              case "THINKING_TEXT_MESSAGE_CONTENT":
              case "THINKING_START":
                this.agentStatus = { show: true, message: "Thinking..." };
                break;
              case "TEXT_MESSAGE_CONTENT":
                this.agentStatus.show = false;
                this.answer.raw += event.delta;
                this.answer.content = marked.parse(this.answer.raw);
                this.answer.show = true;
                break;
              case "RUN_FINISHED":
              case "RUN_ERROR":
                this.agentStatus.show = false;
                this.answer.complete = true;
                break;
            }
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        this.agentStatus.show = false;
      }
    },
    async feedback(event) {
      console.log("Giving feedback...");
      console.log(event.target);
    },
    async submit_feedback_modal(item, itemType, query, feedback, type) {
      if (feedback.length < 10) {
        this.showToast(
          "Feedback Error",
          "Feedback must be at least 10 characters long",
        );
        return;
      }
      this.give_feedback(item, itemType, query, feedback, type);
      if (this.modal.onDone) this.modal.onDone();
      this.modal.text = "";
      this.closeModal();
    },
    async give_feedback(item, itemType, query, feedback, feedbackType) {
      const feedback_obj = {
        query: query,
        item: item,
        itemType: itemType,
        feedback: feedback,
        type: feedbackType,
      };
      console.log(feedback_obj);
      const response = await fetch(`/v1/feedback/submit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(feedback_obj),
      });
      const result = await response.json();
      this.showToast(
        "Feedback Submitted",
        feedbackType + ':"' + feedback + '" for: ' + JSON.stringify(item),
      );
    },
    showToast(title, msg) {
      this.toast.show = true;
      this.toast.title = title;
      this.toast.msg = msg;
      setTimeout(() => {
        this.toast.show = false;
      }, 4000);
    },
    openModal(item, type, onDone = null) {
      this.modal.item = item;
      this.modal.type = type;
      this.modal.onDone = onDone;
      this.modal.show = true;
    },
    closeModal() {
      this.modal.show = false;
    },
    openPrivacyNotice() {
      this.privacyNotice.show = true;
    },
    closePrivacyNotice() {
      this.privacyNotice.show = false;
    },
    groupResults(flat) {
      const groups = {};
      for (const item of flat) {
        const key = item.dataset.uri;
        if (!groups[key]) groups[key] = { dataset: item.dataset, items: [] };
        groups[key].items.push(item);
      }
      return Object.values(groups);
    },
  }));
});
