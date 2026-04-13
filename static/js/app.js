document.addEventListener("alpine:init", () => {
    Alpine.data("app", () => ({
        query: '',
        results: [],
        answer: {
            show: false,
            raw: '',
            content: '',
            complete: false,
        },
        agentStatus: {
            show: false,
            message: '',
        },
        thinking: false,
        splash: true,
        modal: {
            show: false,
            item: '',
            type: '',
            text: '',
        },
        toast: {
            show: false,
            title: 'Toast Title',
            msg: 'Toast Message',
        },
        privacyNotice: {
            show: true,
            accepted: false,
        },
        async search() {
            this.splash = false;
            this.thinking = true;
            this.streamingChat();
            try {
                const response = await fetch(`/query/semantic?q=${this.query}`);
                this.results = await response.json();
            } catch (e) {
                console.error(e);
            } finally {
                this.thinking = false;
            }
        },
        async streamingChat() {
            this.answer = { content: '', complete: false, show: false, raw: '' };
            this.agentStatus = { show: true, message: 'Thinking...' };
            try {
                const response = await fetch('/chat/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: this.query }),
                });
                if (!response.ok) {
                    console.error('Chat stream error:', response.status);
                    return;
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'tool') {
                            this.agentStatus.message = `Using tool: ${event.name}…`;
                        } else if (event.type === 'text') {
                            this.agentStatus.show = false;
                            this.answer.raw += event.delta;
                            this.answer.content = marked.parse(this.answer.raw);
                            this.answer.show = true;
                        } else if (event.type === 'done') {
                            this.agentStatus.show = false;
                            this.answer.complete = true;
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
            console.log('Giving feedback...');
            console.log(event.target);
        },
        async submit_feedback_modal(item, itemType, query, feedback, type) {
            if (feedback.length < 10) {
                this.showToast('Feedback Error', 'Feedback must be at least 10 characters long');
                return;
            }
            this.give_feedback(item, itemType, query, feedback, type);
            this.modal.text = '';
            this.closeModal();
        },
        async give_feedback(item, itemType, query, feedback, feedbackType) {
            const feedback_obj = { "query": query, "item": item, "itemType": itemType, "feedback": feedback, "type": feedbackType };
            console.log(feedback_obj);
            const response = await fetch(`/feedback/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(feedback_obj),
            });
            const result = await response.json();
            this.showToast('Feedback Submitted', feedbackType + ':"' + feedback + '" for: ' + JSON.stringify(item));
        },
        showToast(title, msg) {
            this.toast.show = true;
            this.toast.title = title;
            this.toast.msg = msg;
            setTimeout(() => {
                this.toast.show = false;
            }, 4000);
        },
        openModal(item, type) {
            this.modal.item = item;
            this.modal.type = type;
            this.modal.show = true;
        },
        closeModal() {
            this.modal.show = false;
        },
        openPrivacyNotice() {
            this.privacyNotice.show = true;
        }
        ,
        closePrivacyNotice() {
            this.privacyNotice.show = false;
        }
    }))
})
