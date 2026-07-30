import * as React from "react"
import {
  CheckIcon,
  FileTextIcon,
  LockKeyholeIcon,
  Mic2Icon,
  PanelRightIcon,
  PenLineIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

type PreviewState = "capture" | "review" | "confirmed" | "written"

const EXACT_ANSWER =
  "Clear water has more insects, so it offers fish more food."

export function ProductPreview() {
  const [state, setState] = React.useState<PreviewState>("review")
  const [draft, setDraft] = React.useState(
    "Clear water had more insects, which gives fish more food."
  )
  const visibleTab = state === "written" ? "confirmed" : state

  function changeTab(value: string) {
    if (value === "capture" || value === "review" || value === "confirmed") {
      setState(value)
    }
  }

  return (
    <section className="product-stage" aria-label="Interactive Claros answer preview">
      <div className="stage-bar">
        <div>
          <span className="stage-kicker">Ecosystems worksheet</span>
          <strong>Question 4 of 6</strong>
        </div>
        <Badge variant="outline" className="stage-badge">
          <FileTextIcon aria-hidden="true" />
          Sample
        </Badge>
      </div>

      <div className="product-frame">
        <article className="worksheet-sheet" aria-label="Sample worksheet question">
          <header>
            <span>River health study</span>
            <strong>Cause and effect</strong>
          </header>
          <div className="worksheet-content">
            <p>
              Students counted insects in two streams. The clear stream had
              more insects and more fish.
            </p>
            <h2>Why might the clear stream support more fish?</h2>
            <div className="worksheet-rule" aria-hidden="true" />
            <div className="worksheet-rule short" aria-hidden="true" />
          </div>
          <footer>
            <LockKeyholeIcon aria-hidden="true" />
            Original page unchanged
          </footer>
        </article>

        <Card className="answer-card">
          <CardHeader className="answer-card-header">
            <CardTitle>Your answer</CardTitle>
            <CardDescription>Move through the real safety states.</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={visibleTab} onValueChange={changeTab}>
              <TabsList variant="line" className="preview-tabs" aria-label="Answer state">
                <TabsTrigger value="capture">Capture</TabsTrigger>
                <TabsTrigger value="review">Review</TabsTrigger>
                <TabsTrigger value="confirmed">Confirmed</TabsTrigger>
              </TabsList>

              <TabsContent value="capture" className="state-panel">
                <label htmlFor="preview-draft">Your reasoning</label>
                <Textarea
                  id="preview-draft"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  className="preview-textarea"
                />
                <div className="voice-row">
                  <Button type="button" variant="outline" className="preview-button">
                    <Mic2Icon aria-hidden="true" />
                    Use voice guidance
                  </Button>
                  <span>Voice is optional and starts only when you choose it.</span>
                </div>
                <Button
                  type="button"
                  className="preview-button w-full"
                  onClick={() => setState("review")}
                >
                  Review answer
                </Button>
              </TabsContent>

              <TabsContent value="review" className="state-panel">
                <Badge variant="secondary" className="state-label">
                  Proposed answer
                </Badge>
                <p className="exact-answer">{EXACT_ANSWER}</p>
                <p className="state-note">Confirming does not write to the worksheet.</p>
                <div className="state-actions">
                  <Button
                    type="button"
                    variant="outline"
                    className="preview-button"
                    onClick={() => setState("capture")}
                  >
                    <PenLineIcon aria-hidden="true" />
                    Edit answer
                  </Button>
                  <Button
                    type="button"
                    className="preview-button"
                    onClick={() => setState("confirmed")}
                  >
                    Confirm answer
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="confirmed" className="state-panel" aria-live="polite">
                {state === "written" ? (
                  <>
                    <Badge className="state-label success-label">
                      <CheckIcon aria-hidden="true" />
                      Added to export
                    </Badge>
                    <p className="exact-answer">{EXACT_ANSWER}</p>
                    <div className="destination-line">
                      <PanelRightIcon aria-hidden="true" />
                      <span>
                        <strong>Destination</strong>
                        Export side panel
                      </span>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      className="preview-button w-full"
                      onClick={() => setState("review")}
                    >
                      Start again
                    </Button>
                  </>
                ) : (
                  <>
                    <Badge variant="outline" className="state-label confirmed-label">
                      <LockKeyholeIcon aria-hidden="true" />
                      Confirmed, not written
                    </Badge>
                    <p className="exact-answer">{EXACT_ANSWER}</p>
                    <p className="state-note">The worksheet is still unchanged.</p>
                    <div className="state-actions">
                      <Button
                        type="button"
                        variant="outline"
                        className="preview-button"
                        onClick={() => setState("review")}
                      >
                        Change answer
                      </Button>
                      <Button
                        type="button"
                        className="preview-button"
                        onClick={() => setState("written")}
                      >
                        <PanelRightIcon aria-hidden="true" />
                        Add to export
                      </Button>
                    </div>
                  </>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      <p className="stage-caption">
        Interactive example. This page never changes a worksheet.
      </p>
    </section>
  )
}
